#!/usr/bin/env python3
"""
M2-2: Seasonality Calculator — 132 celdas ETF x mes.
Pobla tabla: seasonality_stats.

Uso:
  python scripts/analyzers/seasonality_calc.py
  python scripts/analyzers/seasonality_calc.py --ticker XLK
"""

import argparse
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import get_db_connection

SECTOR_ETFS = ['XLY', 'XLE', 'XLB', 'XLI', 'XLK', 'XLRE', 'XLP', 'XLV', 'XLF', 'XLU', 'XLC']
MONTH_NAMES = ['', 'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
               'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']


def calculate_seasonality(returns: list) -> dict:
    """Calcula estadísticas de estacionalidad para un set de retornos."""
    arr = np.array([float(r) for r in returns if r is not None])
    if len(arr) == 0:
        return None
    return {
        'avg_return': round(float(np.mean(arr)), 4),
        'win_rate': round(float(np.sum(arr > 0) / len(arr) * 100), 2),
        'best_return': round(float(np.max(arr)), 4),
        'worst_return': round(float(np.min(arr)), 4),
        'years_analyzed': len(arr),
    }


def main():
    parser = argparse.ArgumentParser(description='Seasonality Calculator')
    parser.add_argument('--ticker', type=str, help='Calculate for single ETF')
    args = parser.parse_args()

    conn = get_db_connection()
    cursor = conn.cursor()

    etfs = [args.ticker.upper()] if args.ticker else SECTOR_ETFS

    # Fetch all monthly returns for ETFs
    placeholders = ','.join(['%s'] * len(etfs))
    cursor.execute(f"""
        SELECT ticker, year, month, return_pct
        FROM monthly_returns
        WHERE ticker IN ({placeholders})
        ORDER BY ticker, year, month
    """, etfs)

    # Organize by ticker -> month -> [returns]
    data = {}
    for ticker, year, month, return_pct in cursor.fetchall():
        if ticker not in data:
            data[ticker] = {}
        if month not in data[ticker]:
            data[ticker][month] = []
        if return_pct is not None:
            data[ticker][month].append(float(return_pct))

    # Calculate and insert
    insert_sql = """
        INSERT INTO seasonality_stats
            (ticker, month, avg_return, win_rate, best_return, worst_return, years_analyzed)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE
            avg_return = VALUES(avg_return), win_rate = VALUES(win_rate),
            best_return = VALUES(best_return), worst_return = VALUES(worst_return),
            years_analyzed = VALUES(years_analyzed), last_updated = NOW()
    """

    total_cells = 0
    all_stats = []

    for ticker in etfs:
        if ticker not in data:
            print(f"  ✗ {ticker}: no monthly_returns data")
            continue

        for month in range(1, 13):
            returns = data[ticker].get(month, [])
            if not returns:
                continue

            stats = calculate_seasonality(returns)
            if stats is None:
                continue

            cursor.execute(insert_sql, (
                ticker, month,
                stats['avg_return'], stats['win_rate'],
                stats['best_return'], stats['worst_return'],
                stats['years_analyzed']
            ))
            total_cells += 1
            all_stats.append({
                'ticker': ticker, 'month': month,
                **stats
            })

    conn.commit()

    # Print results
    print(f"=== Seasonality Calculator ===")
    print(f"Processing {len(etfs)} ETFs x 12 months = {len(etfs) * 12} potential cells\n")

    if all_stats:
        # Top 10 by avg_return
        sorted_stats = sorted(all_stats, key=lambda x: x['avg_return'], reverse=True)
        print("Top 10 cells by avg_return:")
        for s in sorted_stats[:10]:
            print(f"  {s['ticker']:<5} - Month {s['month']:>2} ({MONTH_NAMES[s['month']]}): "
                  f"avg={s['avg_return']:+.2f}%, win_rate={s['win_rate']:.0f}%, "
                  f"years={s['years_analyzed']}")

        # High conviction
        high_conv = [s for s in all_stats if s['win_rate'] >= 65]
        print(f"\nHigh conviction cells (win_rate >= 65%): {len(high_conv)} of {total_cells}")

    print(f"\nSaved to seasonality_stats: {total_cells} rows")

    cursor.close()
    conn.close()


if __name__ == '__main__':
    main()
