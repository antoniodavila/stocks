#!/usr/bin/env python3
"""Verifica que todas las tablas del schema existan y muestra conteo de filas."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'scripts'))
from config import get_db_connection

EXPECTED_TABLES = [
    'tickers', 'stock_prices', 'monthly_returns',
    'fundamentals', 'balance_sheet', 'price_ratios',
    'quality_ratios', 'value_scores', 'seasonality_stats',
    'strategies', 'backtest_results', 'backtest_cycles',
    'ai_narratives'
]


def verify_schema():
    conn = get_db_connection()
    cursor = conn.cursor()

    print("seasonal_stocks schema verification:\n")

    found = 0
    missing = 0

    for table in EXPECTED_TABLES:
        try:
            cursor.execute(f"SELECT COUNT(*) FROM `{table}`")
            count = cursor.fetchone()[0]
            print(f"  ✓ {table} ({count} rows)")
            found += 1
        except Exception:
            print(f"  ✗ {table} — MISSING")
            missing += 1

    cursor.close()
    conn.close()

    print()
    if missing == 0:
        print(f"  All {found} tables present ✓")
    else:
        print(f"  {found} tables found, {missing} MISSING ✗")
        sys.exit(1)


if __name__ == '__main__':
    verify_schema()
