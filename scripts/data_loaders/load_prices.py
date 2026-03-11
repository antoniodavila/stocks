#!/usr/bin/env python3
"""
M1-3: Carga histórica de precios S&P 500 (yfinance, 15 años, ~500 tickers).
Pobla tablas: tickers, stock_prices, monthly_returns.

Uso:
  python scripts/data_loaders/load_prices.py
  python scripts/data_loaders/load_prices.py --ticker AAPL
  python scripts/data_loaders/load_prices.py --batch 50 --sleep 1
  python scripts/data_loaders/load_prices.py --resume
"""

import argparse
import logging
import sys
import time
from datetime import datetime
from pathlib import Path

import pandas as pd
import yfinance as yf
from tqdm import tqdm

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import get_db_connection

# Logging
LOG_DIR = Path(__file__).resolve().parent.parent / 'logs'
LOG_DIR.mkdir(exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler(LOG_DIR / 'load_prices.log'),
        logging.StreamHandler()
    ]
)
log = logging.getLogger(__name__)

START_DATE = '2010-01-01'
END_DATE = '2025-12-31'


def get_sp500_tickers() -> pd.DataFrame:
    """Descarga lista S&P 500 desde Wikipedia."""
    import io
    import urllib.request
    url = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (StockAnalyzer/1.0)'})
    html = urllib.request.urlopen(req).read().decode('utf-8')
    df = pd.read_html(io.StringIO(html))[0]
    # Limpiar tickers con puntos (BRK.B -> BRK-B para yfinance)
    df['Symbol_yf'] = df['Symbol'].str.replace('.', '-', regex=False)
    return df


def upsert_tickers(conn, tickers_df: pd.DataFrame):
    """Inserta/actualiza tickers en la tabla tickers."""
    cursor = conn.cursor()
    sql = """
        INSERT INTO tickers (ticker, name, sector, industry, sp500)
        VALUES (%s, %s, %s, %s, TRUE)
        ON DUPLICATE KEY UPDATE
            name = VALUES(name),
            sector = VALUES(sector),
            industry = VALUES(industry),
            sp500 = TRUE
    """
    rows = []
    for _, r in tickers_df.iterrows():
        rows.append((
            r['Symbol'], r['Security'],
            r.get('GICS Sector', ''), r.get('GICS Sub-Industry', '')
        ))
    cursor.executemany(sql, rows)
    conn.commit()
    cursor.close()
    log.info(f"Upserted {len(rows)} tickers")


def get_loaded_tickers(conn) -> set:
    """Retorna set de tickers que ya tienen datos en stock_prices."""
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT ticker FROM stock_prices")
    loaded = {row[0] for row in cursor.fetchall()}
    cursor.close()
    return loaded


def insert_prices(conn, ticker: str, df: pd.DataFrame) -> int:
    """Inserta precios en stock_prices. Retorna cantidad de filas."""
    if df.empty:
        return 0
    cursor = conn.cursor()
    sql = """
        INSERT INTO stock_prices (ticker, date, open, high, low, close, adj_close, volume)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE
            adj_close = VALUES(adj_close), volume = VALUES(volume)
    """
    rows = []
    for date_val, row in df.iterrows():
        date_str = date_val.strftime('%Y-%m-%d') if hasattr(date_val, 'strftime') else str(date_val)[:10]
        rows.append((
            ticker, date_str,
            float(row['Open']) if pd.notna(row['Open']) else None,
            float(row['High']) if pd.notna(row['High']) else None,
            float(row['Low']) if pd.notna(row['Low']) else None,
            float(row['Close']) if pd.notna(row['Close']) else None,
            float(row['Close']) if pd.notna(row['Close']) else None,  # auto_adjust=True -> Close = adj_close
            int(row['Volume']) if pd.notna(row['Volume']) else None,
        ))
    cursor.executemany(sql, rows)
    conn.commit()
    cursor.close()
    return len(rows)


def calc_monthly_returns(conn, ticker: str) -> int:
    """Calcula retornos mensuales desde stock_prices. Retorna filas insertadas."""
    cursor = conn.cursor()
    # Obtener primer y último adj_close por mes
    cursor.execute("""
        SELECT
            YEAR(date) as yr, MONTH(date) as mo,
            (SELECT sp2.adj_close FROM stock_prices sp2
             WHERE sp2.ticker = %s AND YEAR(sp2.date) = YEAR(sp.date) AND MONTH(sp2.date) = MONTH(sp.date)
             ORDER BY sp2.date ASC LIMIT 1) as first_close,
            (SELECT sp3.adj_close FROM stock_prices sp3
             WHERE sp3.ticker = %s AND YEAR(sp3.date) = YEAR(sp.date) AND MONTH(sp3.date) = MONTH(sp.date)
             ORDER BY sp3.date DESC LIMIT 1) as last_close
        FROM stock_prices sp
        WHERE sp.ticker = %s
        GROUP BY YEAR(date), MONTH(date)
    """, (ticker, ticker, ticker))

    rows_data = cursor.fetchall()
    if not rows_data:
        cursor.close()
        return 0

    sql = """
        INSERT INTO monthly_returns (ticker, year, month, return_pct, adj_close_start, adj_close_end)
        VALUES (%s, %s, %s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE
            return_pct = VALUES(return_pct),
            adj_close_start = VALUES(adj_close_start),
            adj_close_end = VALUES(adj_close_end)
    """
    inserts = []
    for yr, mo, first_close, last_close in rows_data:
        if first_close and last_close and float(first_close) > 0:
            ret = (float(last_close) - float(first_close)) / float(first_close) * 100
            inserts.append((ticker, yr, mo, round(ret, 4), float(first_close), float(last_close)))

    if inserts:
        cursor.executemany(sql, inserts)
        conn.commit()
    cursor.close()
    return len(inserts)


def load_single_ticker(conn, ticker_symbol: str, ticker_yf: str) -> dict:
    """Descarga y carga un ticker. Retorna stats."""
    try:
        data = yf.download(ticker_yf, start=START_DATE, end=END_DATE,
                           auto_adjust=True, progress=False)
        if data.empty:
            return {'status': 'empty', 'prices': 0, 'monthly': 0}

        # Si yfinance retorna MultiIndex columns (por batch), aplanar
        if isinstance(data.columns, pd.MultiIndex):
            data.columns = data.columns.get_level_values(0)

        price_rows = insert_prices(conn, ticker_symbol, data)
        monthly_rows = calc_monthly_returns(conn, ticker_symbol)
        return {'status': 'ok', 'prices': price_rows, 'monthly': monthly_rows}
    except Exception as e:
        log.error(f"Error loading {ticker_symbol}: {e}")
        return {'status': 'error', 'prices': 0, 'monthly': 0, 'error': str(e)}


def main():
    parser = argparse.ArgumentParser(description='Load S&P 500 historical prices')
    parser.add_argument('--ticker', type=str, help='Load single ticker')
    parser.add_argument('--batch', type=int, default=50, help='Batch size')
    parser.add_argument('--sleep', type=float, default=1.0, help='Sleep between batches (seconds)')
    parser.add_argument('--resume', action='store_true', help='Skip already loaded tickers')
    args = parser.parse_args()

    start_time = time.time()
    conn = get_db_connection()

    if args.ticker:
        # Modo single ticker — asegurar que existe en tickers
        ticker = args.ticker.upper()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO tickers (ticker, name, sp500, active)
            VALUES (%s, %s, TRUE, TRUE)
            ON DUPLICATE KEY UPDATE active = TRUE
        """, (ticker, ticker))
        conn.commit()
        cursor.close()
        log.info(f"Loading single ticker: {ticker}")
        result = load_single_ticker(conn, ticker, ticker)
        log.info(f"Result: {result}")
        conn.close()
        return

    # Descargar lista S&P 500
    log.info("Fetching S&P 500 ticker list from Wikipedia...")
    tickers_df = get_sp500_tickers()
    log.info(f"Found {len(tickers_df)} tickers")

    # Upsert tickers
    upsert_tickers(conn, tickers_df)

    # Determinar pendientes
    pending = list(zip(tickers_df['Symbol'], tickers_df['Symbol_yf']))
    if args.resume:
        loaded = get_loaded_tickers(conn)
        pending = [(s, yf_s) for s, yf_s in pending if s not in loaded]
        log.info(f"Resume mode: {len(loaded)} already loaded, {len(pending)} pending")

    # Procesar
    total_prices = 0
    total_monthly = 0
    errors = 0

    with tqdm(total=len(pending), desc="Loading prices", unit="ticker") as pbar:
        for i, (symbol, symbol_yf) in enumerate(pending):
            result = load_single_ticker(conn, symbol, symbol_yf)

            if result['status'] == 'ok':
                total_prices += result['prices']
                total_monthly += result['monthly']
            elif result['status'] == 'error':
                errors += 1

            pbar.update(1)
            time.sleep(0.5)

            # Sleep extra entre batches
            if (i + 1) % args.batch == 0:
                time.sleep(args.sleep)

    conn.close()
    elapsed = time.time() - start_time

    print(f"\n=== Price Load Complete ===")
    print(f"Tickers processed: {len(pending)}")
    print(f"Rows inserted (stock_prices): {total_prices:,}")
    print(f"Rows inserted (monthly_returns): {total_monthly:,}")
    print(f"Errors: {errors} (see logs/load_prices.log)")
    print(f"Time elapsed: {int(elapsed // 60)}m {int(elapsed % 60)}s")


if __name__ == '__main__':
    main()
