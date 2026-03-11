#!/usr/bin/env python3
"""
M1-5: Carga de 11 ETFs sectoriales S&P 500 (15 años).
Pobla tablas: tickers, stock_prices, monthly_returns.

Uso:
  python scripts/data_loaders/load_etfs.py
"""

import logging
import sys
import time
from pathlib import Path

import pandas as pd
import yfinance as yf

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import get_db_connection

LOG_DIR = Path(__file__).resolve().parent.parent / 'logs'
LOG_DIR.mkdir(exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler(LOG_DIR / 'load_etfs.log'),
        logging.StreamHandler()
    ]
)
log = logging.getLogger(__name__)

START_DATE = '2010-01-01'
END_DATE = '2025-12-31'

SECTOR_ETFS = [
    ("XLY", "Consumer Discretionary"),
    ("XLE", "Energy"),
    ("XLB", "Materials"),
    ("XLI", "Industrials"),
    ("XLK", "Technology"),
    ("XLRE", "Real Estate"),
    ("XLP", "Consumer Staples"),
    ("XLV", "Health Care"),
    ("XLF", "Financials"),
    ("XLU", "Utilities"),
    ("XLC", "Communication Services"),
]


def upsert_etf_tickers(conn):
    """Inserta los 11 ETFs en tabla tickers con sp500=FALSE."""
    cursor = conn.cursor()
    sql = """
        INSERT INTO tickers (ticker, name, sector, sp500, active)
        VALUES (%s, %s, %s, FALSE, TRUE)
        ON DUPLICATE KEY UPDATE
            name = VALUES(name),
            sector = VALUES(sector)
    """
    for etf, sector in SECTOR_ETFS:
        cursor.execute(sql, (etf, f"{sector} ETF", sector))
    conn.commit()
    cursor.close()
    log.info(f"Upserted {len(SECTOR_ETFS)} ETF tickers")


def insert_prices(conn, ticker: str, df: pd.DataFrame) -> int:
    """Inserta precios en stock_prices."""
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
            float(row['Close']) if pd.notna(row['Close']) else None,
            int(row['Volume']) if pd.notna(row['Volume']) else None,
        ))
    cursor.executemany(sql, rows)
    conn.commit()
    cursor.close()
    return len(rows)


def calc_monthly_returns(conn, ticker: str) -> int:
    """Calcula retornos mensuales desde stock_prices."""
    cursor = conn.cursor()
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


def main():
    start_time = time.time()
    conn = get_db_connection()

    upsert_etf_tickers(conn)

    total_prices = 0
    total_monthly = 0

    print(f"Loading {len(SECTOR_ETFS)} sector ETFs ({START_DATE} to {END_DATE})...\n")

    for etf, sector in SECTOR_ETFS:
        try:
            data = yf.download(etf, start=START_DATE, end=END_DATE,
                               auto_adjust=True, progress=False)

            if isinstance(data.columns, pd.MultiIndex):
                data.columns = data.columns.get_level_values(0)

            price_rows = insert_prices(conn, etf, data)
            monthly_rows = calc_monthly_returns(conn, etf)
            total_prices += price_rows
            total_monthly += monthly_rows

            note = ""
            if etf == "XLC" and not data.empty:
                first_date = data.index[0].strftime('%Y-%m')
                note = f" (desde {first_date})"

            print(f"  ✓ {etf} - {sector}: {price_rows:,} price rows, {monthly_rows} monthly returns{note}")
            time.sleep(0.5)

        except Exception as e:
            log.error(f"Error loading {etf}: {e}")
            print(f"  ✗ {etf} - {sector}: ERROR - {e}")

    conn.close()
    elapsed = time.time() - start_time

    print(f"\n=== ETF Load Complete ===")
    print(f"Total price rows: {total_prices:,}")
    print(f"Total monthly return rows: {total_monthly:,}")
    print(f"Time elapsed: {int(elapsed // 60)}m {int(elapsed % 60)}s")


if __name__ == '__main__':
    main()
