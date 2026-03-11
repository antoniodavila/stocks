#!/usr/bin/env python3
"""Muestra el heatmap de estacionalidad como tabla ASCII en consola."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import get_db_connection

SECTOR_ETFS = ['XLY', 'XLE', 'XLB', 'XLI', 'XLK', 'XLRE', 'XLP', 'XLV', 'XLF', 'XLU', 'XLC']
MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

# ANSI colors
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
RESET = '\033[0m'


def main():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT ticker, month, avg_return, win_rate, years_analyzed
        FROM seasonality_stats
        ORDER BY ticker, month
    """)

    # Organize data
    data = {}
    for row in cursor.fetchall():
        t = row['ticker']
        if t not in data:
            data[t] = {}
        data[t][row['month']] = row

    cursor.close()
    conn.close()

    # Print header
    header = f"{'ETF':<6}|" + "|".join(f" {m:>5} " for m in MONTHS)
    separator = "-" * len(header)
    print("\n  Seasonality Heatmap — avg_return (%) | color = win_rate\n")
    print(f"  {header}")
    print(f"  {separator}")

    for etf in SECTOR_ETFS:
        row_str = f"  {etf:<6}|"
        if etf not in data:
            row_str += " no data"
            print(row_str)
            continue

        for month in range(1, 13):
            cell = data[etf].get(month)
            if cell is None:
                row_str += "   —   |"
                continue

            val = float(cell['avg_return'])
            wr = float(cell['win_rate'])

            # Color based on win_rate
            if wr >= 65:
                color = GREEN
            elif wr < 40:
                color = RED
            else:
                color = YELLOW

            row_str += f"{color} {val:>5.1f} {RESET}|"

        print(row_str)

    print(f"\n  {GREEN}Green{RESET}=win_rate>=65% | {YELLOW}Yellow{RESET}=40-65% | {RED}Red{RESET}=<40%")
    print()


if __name__ == '__main__':
    main()
