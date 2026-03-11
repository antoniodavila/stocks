#!/usr/bin/env python3
"""
M1-4: Carga de fundamentales S&P 500 (EDGAR waterfall + FMP + Alpha Vantage).
Pobla tablas: fundamentals, balance_sheet, price_ratios, quality_ratios.

Uso:
  python scripts/data_loaders/load_fundamentals.py
  python scripts/data_loaders/load_fundamentals.py --ticker AAPL
  python scripts/data_loaders/load_fundamentals.py --resume
  python scripts/data_loaders/load_fundamentals.py --source edgar
"""

import argparse
import json
import logging
import sys
import time
from datetime import date, datetime
from pathlib import Path

import requests
import yfinance as yf
from tqdm import tqdm

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import (get_db_connection, FMP_API_KEY, ALPHA_VANTAGE_API_KEY)

LOG_DIR = Path(__file__).resolve().parent.parent / 'logs'
LOG_DIR.mkdir(exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler(LOG_DIR / 'load_fundamentals.log'),
        logging.StreamHandler()
    ]
)
log = logging.getLogger(__name__)

EDGAR_HEADERS = {'User-Agent': 'seasonal-stocks-app admin@seasonal-stocks.local'}

# Counters for API rate limits
fmp_requests_today = 0
av_requests_today = 0

# XBRL tags for fundamentals
XBRL_TAGS = {
    'revenue': ['Revenues', 'RevenueFromContractWithCustomerExcludingAssessedTax',
                'SalesRevenueNet', 'RevenueFromContractWithCustomerIncludingAssessedTax'],
    'net_income': ['NetIncomeLoss', 'ProfitLoss'],
    'eps_diluted': ['EarningsPerShareDiluted'],
    'gross_profit': ['GrossProfit'],
    'operating_income': ['OperatingIncomeLoss'],
    'operating_cf': ['NetCashProvidedByUsedInOperatingActivities',
                     'NetCashProvidedByUsedInOperatingActivitiesContinuingOperations'],
    'capex': ['PaymentsToAcquirePropertyPlantAndEquipment'],
    'shares_diluted': ['WeightedAverageNumberOfDilutedSharesOutstanding',
                       'CommonStockSharesOutstanding'],
}

BALANCE_TAGS = {
    'total_assets': ['Assets'],
    'total_equity': ['StockholdersEquity',
                     'StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest'],
    'long_term_debt': ['LongTermDebt', 'LongTermDebtNoncurrent'],
    'short_term_debt': ['ShortTermBorrowings', 'NotesPayableCurrent', 'LongTermDebtCurrent'],
    'current_assets': ['AssetsCurrent'],
    'current_liabilities': ['LiabilitiesCurrent'],
    'cash_and_equivalents': ['CashAndCashEquivalentsAtCarryingValue',
                             'CashCashEquivalentsAndShortTermInvestments'],
    'retained_earnings': ['RetainedEarningsAccumulatedDeficit'],
    'interest_expense': ['InterestExpense', 'InterestExpenseDebt'],
}


# ─── CIK MAPPING ───────────────────────────────────────────────

_cik_map = None

def get_cik_map() -> dict:
    """Descarga mapping ticker -> CIK desde SEC."""
    global _cik_map
    if _cik_map is not None:
        return _cik_map
    url = "https://www.sec.gov/files/company_tickers.json"
    resp = requests.get(url, headers=EDGAR_HEADERS)
    resp.raise_for_status()
    data = resp.json()
    _cik_map = {}
    for entry in data.values():
        _cik_map[entry['ticker'].upper()] = str(entry['cik_str'])
    return _cik_map


# ─── EDGAR EXTRACTION ──────────────────────────────────────────

def get_edgar_facts(cik: str) -> dict:
    url = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik.zfill(10)}.json"
    time.sleep(0.1)
    resp = requests.get(url, headers=EDGAR_HEADERS)
    if resp.status_code != 200:
        return {}
    return resp.json()


def extract_concept(facts: dict, tag_list: list) -> list:
    """Extrae valores de un concepto XBRL. Retorna lista de dicts con end, val, form, filed."""
    us_gaap = facts.get('facts', {}).get('us-gaap', {})
    for tag in tag_list:
        if tag in us_gaap:
            units = us_gaap[tag].get('units', {})
            for unit_key in ['USD', 'shares', 'USD/shares', 'pure']:
                if unit_key in units:
                    items = [item for item in units[unit_key]
                             if item.get('form') in ('10-Q', '10-K')
                             and 'end' in item and 'val' in item]
                    if items:
                        return items
    return []


def dedupe_filings(items: list) -> list:
    """Deduplica por (end, form), tomando el más reciente por filed."""
    seen = {}
    for item in items:
        key = (item['end'], item.get('form', ''))
        if key not in seen or item.get('filed', '') > seen[key].get('filed', ''):
            seen[key] = item
    return sorted(seen.values(), key=lambda x: x['end'])


def process_edgar_data(conn, ticker: str, facts: dict):
    """Procesa datos EDGAR y los inserta en fundamentals y balance_sheet."""
    cursor = conn.cursor()

    # ── Fundamentals ──
    concepts = {}
    for field, tags in XBRL_TAGS.items():
        raw = extract_concept(facts, tags)
        concepts[field] = dedupe_filings(raw)

    # Recopilar todas las fechas de período con datos
    all_periods = set()
    for field, items in concepts.items():
        for item in items:
            all_periods.add((item['end'], item.get('form', '10-Q')))

    fund_sql = """
        INSERT INTO fundamentals (ticker, period, period_type, revenue, net_income, eps_diluted,
            gross_profit, operating_income, ebitda, fcf, operating_cf, capex, shares_diluted, source)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'edgar')
        ON DUPLICATE KEY UPDATE
            revenue = VALUES(revenue), net_income = VALUES(net_income),
            eps_diluted = VALUES(eps_diluted), gross_profit = VALUES(gross_profit),
            operating_income = VALUES(operating_income), ebitda = VALUES(ebitda),
            fcf = VALUES(fcf), operating_cf = VALUES(operating_cf),
            capex = VALUES(capex), shares_diluted = VALUES(shares_diluted)
    """

    fund_count = 0
    for period_end, form in sorted(all_periods):
        period_type = 'A' if form == '10-K' else 'Q'

        def get_val(field):
            for item in concepts.get(field, []):
                if item['end'] == period_end:
                    return item['val']
            return None

        rev = get_val('revenue')
        ni = get_val('net_income')
        eps = get_val('eps_diluted')
        gp = get_val('gross_profit')
        oi = get_val('operating_income')
        ocf = get_val('operating_cf')
        capex_val = get_val('capex')
        shares = get_val('shares_diluted')

        # Calcular FCF y EBITDA
        fcf = None
        if ocf is not None and capex_val is not None:
            fcf = int(ocf) - int(capex_val)

        ebitda = None  # No calculamos EBITDA aquí por simplicidad

        # Solo insertar si hay al menos revenue o net_income
        if rev is not None or ni is not None:
            cursor.execute(fund_sql, (
                ticker, period_end, period_type,
                rev, ni, eps, gp, oi, ebitda, fcf, ocf, capex_val, shares
            ))
            fund_count += 1

    # ── Balance Sheet ──
    balance_concepts = {}
    for field, tags in BALANCE_TAGS.items():
        raw = extract_concept(facts, tags)
        balance_concepts[field] = dedupe_filings(raw)

    bal_periods = set()
    for field, items in balance_concepts.items():
        for item in items:
            bal_periods.add(item['end'])

    bal_sql = """
        INSERT INTO balance_sheet (ticker, period, total_assets, total_equity, total_debt,
            long_term_debt, short_term_debt, current_assets, current_liabilities,
            cash_and_equivalents, retained_earnings, source)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'edgar')
        ON DUPLICATE KEY UPDATE
            total_assets = VALUES(total_assets), total_equity = VALUES(total_equity),
            total_debt = VALUES(total_debt), long_term_debt = VALUES(long_term_debt),
            short_term_debt = VALUES(short_term_debt), current_assets = VALUES(current_assets),
            current_liabilities = VALUES(current_liabilities),
            cash_and_equivalents = VALUES(cash_and_equivalents),
            retained_earnings = VALUES(retained_earnings)
    """

    bal_count = 0
    for period_end in sorted(bal_periods):
        def get_bal(field):
            for item in balance_concepts.get(field, []):
                if item['end'] == period_end:
                    return item['val']
            return None

        ta = get_bal('total_assets')
        te = get_bal('total_equity')
        ltd = get_bal('long_term_debt')
        std = get_bal('short_term_debt')
        td = None
        if ltd is not None or std is not None:
            td = (int(ltd) if ltd else 0) + (int(std) if std else 0)
        ca = get_bal('current_assets')
        cl = get_bal('current_liabilities')
        cash = get_bal('cash_and_equivalents')
        re_val = get_bal('retained_earnings')

        if ta is not None or te is not None:
            cursor.execute(bal_sql, (
                ticker, period_end, ta, te, td, ltd, std, ca, cl, cash, re_val
            ))
            bal_count += 1

    conn.commit()

    # ── Quality Ratios ──
    calc_quality_ratios(conn, ticker)

    cursor.close()
    return fund_count, bal_count


# ─── FMP EXTRACTION ────────────────────────────────────────────

def get_fmp_financials(ticker: str, period: str = 'quarter') -> dict:
    global fmp_requests_today
    if not FMP_API_KEY:
        return {}
    base = "https://financialmodelingprep.com/api/v3"
    result = {}
    for stmt in ['income-statement', 'balance-sheet-statement', 'cash-flow-statement']:
        url = f"{base}/{stmt}/{ticker}?period={period}&limit=20&apikey={FMP_API_KEY}"
        resp = requests.get(url)
        fmp_requests_today += 1
        key = stmt.split('-')[0]  # income, balance, cash
        result[key] = resp.json() if resp.status_code == 200 else []
        time.sleep(0.5)
    return result


def process_fmp_data(conn, ticker: str, data: dict):
    """Procesa datos FMP e inserta en fundamentals y balance_sheet."""
    cursor = conn.cursor()
    fund_count = 0
    bal_count = 0

    # Fundamentals from income + cash flow
    income_items = data.get('income', [])
    cashflow_map = {}
    for cf in data.get('cash', []):
        cashflow_map[cf.get('date', '')[:10]] = cf

    for item in income_items:
        period = item.get('date', '')[:10]
        if not period:
            continue
        period_type = 'A' if item.get('period') == 'FY' else 'Q'
        cf = cashflow_map.get(period, {})
        ocf = cf.get('operatingCashFlow')
        capex_val = cf.get('capitalExpenditure')
        fcf = None
        if ocf is not None and capex_val is not None:
            fcf = int(ocf) + int(capex_val)  # FMP capex is negative

        cursor.execute("""
            INSERT INTO fundamentals (ticker, period, period_type, revenue, net_income, eps_diluted,
                gross_profit, operating_income, ebitda, fcf, operating_cf, capex, shares_diluted, source)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'fmp')
            ON DUPLICATE KEY UPDATE
                revenue = VALUES(revenue), net_income = VALUES(net_income),
                source = 'fmp'
        """, (
            ticker, period, period_type,
            item.get('revenue'), item.get('netIncome'), item.get('epsdiluted'),
            item.get('grossProfit'), item.get('operatingIncome'), item.get('ebitda'),
            fcf, ocf, capex_val, item.get('weightedAverageShsOutDil')
        ))
        fund_count += 1

    # Balance sheet
    for item in data.get('balance', []):
        period = item.get('date', '')[:10]
        if not period:
            continue
        ltd = item.get('longTermDebt', 0) or 0
        std = item.get('shortTermDebt', 0) or 0
        td = ltd + std

        cursor.execute("""
            INSERT INTO balance_sheet (ticker, period, total_assets, total_equity, total_debt,
                long_term_debt, short_term_debt, current_assets, current_liabilities,
                cash_and_equivalents, retained_earnings, source)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'fmp')
            ON DUPLICATE KEY UPDATE
                total_assets = VALUES(total_assets), source = 'fmp'
        """, (
            ticker, period,
            item.get('totalAssets'), item.get('totalStockholdersEquity'), td,
            item.get('longTermDebt'), item.get('shortTermDebt'),
            item.get('totalCurrentAssets'), item.get('totalCurrentLiabilities'),
            item.get('cashAndCashEquivalents'), item.get('retainedEarnings')
        ))
        bal_count += 1

    conn.commit()
    calc_quality_ratios(conn, ticker)
    cursor.close()
    return fund_count, bal_count


# ─── ALPHA VANTAGE EXTRACTION ──────────────────────────────────

def get_av_fundamentals(ticker: str) -> dict:
    global av_requests_today
    if not ALPHA_VANTAGE_API_KEY:
        return {}
    base = "https://www.alphavantage.co/query"
    result = {}
    for func in ['INCOME_STATEMENT', 'BALANCE_SHEET']:
        resp = requests.get(f"{base}?function={func}&symbol={ticker}&apikey={ALPHA_VANTAGE_API_KEY}")
        av_requests_today += 1
        result[func.lower()] = resp.json() if resp.status_code == 200 else {}
        time.sleep(15)
    return result


def process_av_data(conn, ticker: str, data: dict):
    """Procesa datos Alpha Vantage (simplificado, solo gaps)."""
    cursor = conn.cursor()
    fund_count = 0

    for report in data.get('income_statement', {}).get('quarterlyReports', []):
        period = report.get('fiscalDateEnding', '')[:10]
        if not period:
            continue
        cursor.execute("""
            INSERT INTO fundamentals (ticker, period, period_type, revenue, net_income,
                gross_profit, operating_income, source)
            VALUES (%s, %s, 'Q', %s, %s, %s, %s, 'alpha_vantage')
            ON DUPLICATE KEY UPDATE source = source
        """, (
            ticker, period,
            report.get('totalRevenue') if report.get('totalRevenue') != 'None' else None,
            report.get('netIncome') if report.get('netIncome') != 'None' else None,
            report.get('grossProfit') if report.get('grossProfit') != 'None' else None,
            report.get('operatingIncome') if report.get('operatingIncome') != 'None' else None,
        ))
        fund_count += 1

    conn.commit()
    cursor.close()
    return fund_count


# ─── QUALITY RATIOS ────────────────────────────────────────────

def calc_quality_ratios(conn, ticker: str):
    """Calcula quality_ratios desde fundamentals + balance_sheet."""
    cursor = conn.cursor()

    # Obtener fundamentals + balance_sheet join por period
    cursor.execute("""
        SELECT f.period, f.net_income, f.gross_profit, f.revenue, f.operating_income,
               b.total_equity, b.total_debt, b.cash_and_equivalents,
               b.current_assets, b.current_liabilities, b.total_assets
        FROM fundamentals f
        LEFT JOIN balance_sheet b ON b.ticker = f.ticker AND b.period = f.period
        WHERE f.ticker = %s
        ORDER BY f.period
    """, (ticker,))

    rows = cursor.fetchall()
    prev_equity = None

    sql = """
        INSERT INTO quality_ratios (ticker, period, roe, roic, gross_margin,
            operating_margin, net_margin, debt_equity, current_ratio, asset_turnover)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE
            roe = VALUES(roe), roic = VALUES(roic), gross_margin = VALUES(gross_margin),
            operating_margin = VALUES(operating_margin), net_margin = VALUES(net_margin),
            debt_equity = VALUES(debt_equity), current_ratio = VALUES(current_ratio),
            asset_turnover = VALUES(asset_turnover)
    """

    for row in rows:
        period, ni, gp, rev, oi, equity, debt, cash, ca, cl, ta = row

        def safe_div(a, b):
            if a is not None and b is not None and float(b) != 0:
                return round(float(a) / float(b), 4)
            return None

        # ROE
        roe = None
        if ni is not None and equity is not None and prev_equity is not None:
            avg_eq = (float(equity) + float(prev_equity)) / 2
            if avg_eq != 0:
                roe = round(float(ni) / avg_eq, 4)
        elif ni is not None and equity is not None and float(equity) != 0:
            roe = round(float(ni) / float(equity), 4)

        # ROIC
        roic = None
        if oi is not None and equity is not None:
            nopat = float(oi) * (1 - 0.21)
            debt_val = float(debt) if debt else 0
            cash_val = float(cash) if cash else 0
            ic = float(equity) + debt_val - cash_val
            if ic != 0:
                roic = round(nopat / ic, 4)

        gross_margin = safe_div(gp, rev)
        op_margin = safe_div(oi, rev)
        net_margin = safe_div(ni, rev)
        de = safe_div(debt, equity)
        cr = safe_div(ca, cl)
        at = safe_div(rev, ta)

        cursor.execute(sql, (ticker, period, roe, roic, gross_margin,
                             op_margin, net_margin, de, cr, at))

        prev_equity = equity

    conn.commit()
    cursor.close()


# ─── PRICE RATIOS ──────────────────────────────────────────────

def load_price_ratios(conn, ticker: str):
    """Carga ratios de precio desde yfinance.info."""
    try:
        info = yf.Ticker(ticker).info
        cursor = conn.cursor()
        today = date.today().isoformat()

        cursor.execute("""
            INSERT INTO price_ratios (ticker, date, pe_ratio, pb_ratio, pfcf_ratio,
                ev_ebitda, market_cap, enterprise_value)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                pe_ratio = VALUES(pe_ratio), pb_ratio = VALUES(pb_ratio),
                pfcf_ratio = VALUES(pfcf_ratio), ev_ebitda = VALUES(ev_ebitda),
                market_cap = VALUES(market_cap), enterprise_value = VALUES(enterprise_value)
        """, (
            ticker, today,
            info.get('trailingPE'),
            info.get('priceToBook'),
            info.get('priceToFreeCashflow') or info.get('priceToFreeCashFlows'),
            info.get('enterpriseToEbitda'),
            info.get('marketCap'),
            info.get('enterpriseValue'),
        ))
        conn.commit()
        cursor.close()
        time.sleep(0.3)
    except Exception as e:
        log.warning(f"Price ratios failed for {ticker}: {e}")


# ─── MAIN WATERFALL ────────────────────────────────────────────

def load_ticker_fundamentals(conn, ticker: str, cik: str, source_filter: str = None) -> str:
    """Carga fundamentales con waterfall. Retorna fuente usada."""
    global fmp_requests_today, av_requests_today

    # Intento 1: EDGAR
    if source_filter in (None, 'edgar'):
        try:
            facts = get_edgar_facts(cik)
            if facts and 'facts' in facts:
                fc, bc = process_edgar_data(conn, ticker, facts)
                if fc > 0:
                    return 'edgar'
        except Exception as e:
            log.warning(f"EDGAR failed for {ticker}: {e}")

    # Intento 2: FMP
    if source_filter in (None, 'fmp') and fmp_requests_today < 240:
        try:
            data = get_fmp_financials(ticker)
            if data.get('income'):
                fc, bc = process_fmp_data(conn, ticker, data)
                if fc > 0:
                    return 'fmp'
        except Exception as e:
            log.warning(f"FMP failed for {ticker}: {e}")

    # Intento 3: Alpha Vantage
    if source_filter in (None, 'alpha_vantage') and av_requests_today < 20:
        try:
            data = get_av_fundamentals(ticker)
            if data:
                fc = process_av_data(conn, ticker, data)
                if fc > 0:
                    return 'alpha_vantage'
        except Exception as e:
            log.warning(f"AV failed for {ticker}: {e}")

    return 'failed'


def get_processed_tickers(conn) -> set:
    """Retorna tickers que ya tienen fundamentals."""
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT ticker FROM fundamentals")
    result = {row[0] for row in cursor.fetchall()}
    cursor.close()
    return result


def main():
    parser = argparse.ArgumentParser(description='Load S&P 500 fundamentals')
    parser.add_argument('--ticker', type=str, help='Load single ticker')
    parser.add_argument('--resume', action='store_true', help='Skip already loaded tickers')
    parser.add_argument('--source', type=str, choices=['edgar', 'fmp', 'alpha_vantage'],
                        help='Force specific source')
    args = parser.parse_args()

    start_time = time.time()
    conn = get_db_connection()

    # Get CIK mapping
    log.info("Loading SEC CIK mapping...")
    cik_map = get_cik_map()
    log.info(f"CIK map loaded: {len(cik_map)} entries")

    if args.ticker:
        ticker = args.ticker.upper()
        cik = cik_map.get(ticker, '')
        if not cik:
            log.error(f"No CIK found for {ticker}")
            return
        source = load_ticker_fundamentals(conn, ticker, cik, args.source)
        load_price_ratios(conn, ticker)
        log.info(f"{ticker}: loaded via {source}")
        conn.close()
        return

    # Get all S&P 500 tickers from DB
    cursor = conn.cursor()
    cursor.execute("SELECT ticker FROM tickers WHERE sp500 = TRUE AND active = TRUE")
    all_tickers = [row[0] for row in cursor.fetchall()]
    cursor.close()

    if not all_tickers:
        log.error("No tickers in DB. Run load_prices.py first to populate tickers table.")
        conn.close()
        return

    pending = all_tickers
    if args.resume:
        processed = get_processed_tickers(conn)
        pending = [t for t in all_tickers if t not in processed]
        log.info(f"Resume: {len(processed)} done, {len(pending)} pending")

    # Stats
    stats = {'edgar': 0, 'fmp': 0, 'alpha_vantage': 0, 'failed': 0}
    fund_total = 0
    bal_total = 0

    with tqdm(total=len(pending), desc="Loading fundamentals", unit="ticker") as pbar:
        for ticker in pending:
            cik = cik_map.get(ticker, '')
            if not cik:
                log.warning(f"No CIK for {ticker}, trying FMP/AV")
                cik = ''

            source = load_ticker_fundamentals(conn, ticker, cik, args.source)
            stats[source] += 1

            # Price ratios
            load_price_ratios(conn, ticker)

            pbar.update(1)

    # Count final rows
    cursor = conn.cursor()
    for table in ['fundamentals', 'balance_sheet', 'price_ratios', 'quality_ratios']:
        cursor.execute(f"SELECT COUNT(*) FROM {table}")
        count = cursor.fetchone()[0]
        log.info(f"  {table}: {count:,} rows")
    cursor.close()

    conn.close()
    elapsed = time.time() - start_time

    total = sum(stats.values())
    print(f"\n=== Fundamentals Load Complete ===")
    print(f"Tickers processed: {total}")
    print(f"  EDGAR primary:      {stats['edgar']} ({stats['edgar']*100//max(total,1)}%)")
    print(f"  FMP fallback:       {stats['fmp']} ({stats['fmp']*100//max(total,1)}%)")
    print(f"  Alpha Vantage:      {stats['alpha_vantage']} ({stats['alpha_vantage']*100//max(total,1)}%)")
    print(f"  Failed:             {stats['failed']} ({stats['failed']*100//max(total,1)}%)")
    print(f"Errors: see logs/load_fundamentals.log")
    print(f"Time elapsed: {int(elapsed // 60)}m {int(elapsed % 60)}s")


if __name__ == '__main__':
    main()
