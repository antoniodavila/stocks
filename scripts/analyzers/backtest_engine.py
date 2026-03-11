#!/usr/bin/env python3
"""
M2-3: Backtest Engine — 100% SQL local, sin llamadas externas.
Pobla tablas: strategies, backtest_results, backtest_cycles.

Uso:
  python scripts/analyzers/backtest_engine.py --ticker XLK --entry-month 11 --entry-day first --exit-month 4 --exit-day last --capital 10000 --year-start 2010 --year-end 2024
  python scripts/analyzers/backtest_engine.py --ticker XLK --all-combinations
  python scripts/analyzers/backtest_engine.py --strategy-id 5
"""

import argparse
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import get_db_connection


def get_trading_day(cursor, ticker: str, year: int, month: int, day_type: str):
    """Retorna (date, price) del primer o último día hábil del mes."""
    order = 'ASC' if day_type == 'first' else 'DESC'
    cursor.execute(f"""
        SELECT date, adj_close FROM stock_prices
        WHERE ticker = %s AND YEAR(date) = %s AND MONTH(date) = %s
        ORDER BY date {order} LIMIT 1
    """, (ticker, year, month))
    row = cursor.fetchone()
    if row:
        return row[0], float(row[1])
    return None, None


def calculate_buyhold(cursor, ticker: str, entry_date, exit_date) -> float:
    """Retorno buy & hold entre dos fechas."""
    cursor.execute("""
        SELECT adj_close FROM stock_prices
        WHERE ticker = %s AND date >= %s ORDER BY date ASC LIMIT 1
    """, (ticker, entry_date))
    start_row = cursor.fetchone()

    cursor.execute("""
        SELECT adj_close FROM stock_prices
        WHERE ticker = %s AND date <= %s ORDER BY date DESC LIMIT 1
    """, (ticker, exit_date))
    end_row = cursor.fetchone()

    if start_row and end_row and float(start_row[0]) > 0:
        return (float(end_row[0]) - float(start_row[0])) / float(start_row[0]) * 100
    return 0.0


def run_backtest(conn, params: dict) -> tuple:
    """Ejecuta backtest. Retorna (cycles, metrics)."""
    cursor = conn.cursor()
    ticker = params['ticker']
    cycles = []
    capital = params['initial_capital']

    for year in range(params['year_start'], params['year_end'] + 1):
        # Si exit_month <= entry_month, la salida es al año siguiente
        exit_year = year + 1 if params['exit_month'] <= params['entry_month'] else year

        entry_date, entry_price = get_trading_day(
            cursor, ticker, year, params['entry_month'], params['entry_day'])
        exit_date, exit_price = get_trading_day(
            cursor, ticker, exit_year, params['exit_month'], params['exit_day'])

        if not entry_price or not exit_price:
            continue

        cycle_return = (exit_price - entry_price) / entry_price * 100
        capital_start = capital
        capital = capital * (1 + cycle_return / 100)

        buyhold_return = calculate_buyhold(cursor, ticker, entry_date, exit_date)

        cycles.append({
            'year': year,
            'entry_date': entry_date,
            'exit_date': exit_date,
            'entry_price': entry_price,
            'exit_price': exit_price,
            'return_pct': round(cycle_return, 4),
            'capital_start': round(capital_start, 2),
            'capital_end': round(capital, 2),
            'buyhold_return': round(buyhold_return, 4),
        })

    cursor.close()

    if not cycles:
        return cycles, {}

    # Aggregate metrics
    returns = [c['return_pct'] for c in cycles]
    returns_arr = np.array(returns)
    final_capital = cycles[-1]['capital_end']
    initial = params['initial_capital']
    n_years = len(cycles)

    # CAGR
    cagr = ((final_capital / initial) ** (1 / n_years) - 1) * 100 if n_years > 0 else 0

    # Max drawdown
    peak = initial
    max_dd = 0
    for c in cycles:
        if c['capital_end'] > peak:
            peak = c['capital_end']
        dd = (peak - c['capital_end']) / peak * 100
        if dd > max_dd:
            max_dd = dd

    # Sharpe (risk-free = 2%)
    excess = returns_arr - 2.0
    sharpe = float(np.mean(excess) / np.std(excess)) if np.std(excess) > 0 else 0

    metrics = {
        'total_return': round((final_capital - initial) / initial * 100, 4),
        'cagr': round(cagr, 4),
        'win_rate': round(sum(1 for r in returns if r > 0) / len(returns) * 100, 2),
        'avg_cycle_return': round(float(np.mean(returns)), 4),
        'best_year_return': round(max(returns), 4),
        'worst_year_return': round(min(returns), 4),
        'max_drawdown': round(max_dd, 4),
        'sharpe_ratio': round(sharpe, 4),
        'total_cycles': len(cycles),
        'winning_cycles': sum(1 for r in returns if r > 0),
    }

    return cycles, metrics


def save_to_db(conn, params: dict, cycles: list, metrics: dict) -> int:
    """Guarda estrategia, resultados y ciclos. Retorna strategy_id."""
    cursor = conn.cursor()

    # Insert strategy
    cursor.execute("""
        INSERT INTO strategies (ticker, entry_month, entry_day_type, exit_month, exit_day_type,
            initial_capital, year_start, year_end, name)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
    """, (
        params['ticker'], params['entry_month'], params['entry_day'],
        params['exit_month'], params['exit_day'],
        params['initial_capital'], params['year_start'], params['year_end'],
        params.get('name', f"{params['ticker']} M{params['entry_month']}-M{params['exit_month']}")
    ))
    strategy_id = cursor.lastrowid

    # Insert results
    cursor.execute("""
        INSERT INTO backtest_results (strategy_id, total_return, cagr, win_rate,
            avg_cycle_return, best_year_return, worst_year_return,
            max_drawdown, sharpe_ratio, total_cycles, winning_cycles)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """, (
        strategy_id, metrics['total_return'], metrics['cagr'], metrics['win_rate'],
        metrics['avg_cycle_return'], metrics['best_year_return'],
        metrics['worst_year_return'], metrics['max_drawdown'],
        metrics['sharpe_ratio'], metrics['total_cycles'], metrics['winning_cycles']
    ))

    # Insert cycles
    for c in cycles:
        cursor.execute("""
            INSERT INTO backtest_cycles (strategy_id, year, entry_date, exit_date,
                entry_price, exit_price, return_pct, capital_start, capital_end, buyhold_return)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            strategy_id, c['year'], c['entry_date'], c['exit_date'],
            c['entry_price'], c['exit_price'], c['return_pct'],
            c['capital_start'], c['capital_end'], c['buyhold_return']
        ))

    conn.commit()
    cursor.close()
    return strategy_id


def print_results(params: dict, cycles: list, metrics: dict):
    """Imprime resultados formateados."""
    print(f"\n=== Backtest Engine ===")
    print(f"Strategy: {params['ticker']} | Entry: "
          f"M{params['entry_month']} {params['entry_day']} | Exit: "
          f"M{params['exit_month']} {params['exit_day']} | "
          f"Capital: ${params['initial_capital']:,.0f} | "
          f"{params['year_start']}-{params['year_end']}")

    print(f"\n{'Year':>4}  {'Entry Date':>12}  {'Entry $':>9}  "
          f"{'Exit Date':>12}  {'Exit $':>9}  {'Return':>8}  {'Capital':>10}")
    print("-" * 80)

    for c in cycles:
        print(f"{c['year']:>4}  {str(c['entry_date']):>12}  "
              f"${c['entry_price']:>8.2f}  {str(c['exit_date']):>12}  "
              f"${c['exit_price']:>8.2f}  {c['return_pct']:>+7.1f}%  "
              f"${c['capital_end']:>9,.0f}")

    print(f"\n=== Aggregate Results ===")
    print(f"Total Return:     {metrics['total_return']:+.1f}%")
    print(f"CAGR:             {metrics['cagr']:+.1f}%")
    print(f"Win Rate:         {metrics['win_rate']:.0f}% "
          f"({metrics['winning_cycles']}/{metrics['total_cycles']} cycles)")
    print(f"Avg Cycle Return: {metrics['avg_cycle_return']:+.1f}%")
    print(f"Best Year:        {metrics['best_year_return']:+.1f}%")
    print(f"Worst Year:       {metrics['worst_year_return']:+.1f}%")
    print(f"Max Drawdown:     {metrics['max_drawdown']:.1f}%")
    print(f"Sharpe Ratio:     {metrics['sharpe_ratio']:.2f}")


def main():
    parser = argparse.ArgumentParser(description='Backtest Engine')
    parser.add_argument('--ticker', type=str, help='Ticker symbol')
    parser.add_argument('--entry-month', type=int, help='Entry month (1-12)')
    parser.add_argument('--entry-day', type=str, default='first', choices=['first', 'last'])
    parser.add_argument('--exit-month', type=int, help='Exit month (1-12)')
    parser.add_argument('--exit-day', type=str, default='last', choices=['first', 'last'])
    parser.add_argument('--capital', type=float, default=10000)
    parser.add_argument('--year-start', type=int, default=2010)
    parser.add_argument('--year-end', type=int, default=2024)
    parser.add_argument('--all-combinations', action='store_true',
                        help='Run all 132 entry/exit month combinations')
    parser.add_argument('--strategy-id', type=int, help='Re-run existing strategy')
    args = parser.parse_args()

    conn = get_db_connection()

    if args.strategy_id:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM strategies WHERE id = %s", (args.strategy_id,))
        s = cursor.fetchone()
        cursor.close()
        if not s:
            print(f"Strategy {args.strategy_id} not found")
            return
        params = {
            'ticker': s['ticker'], 'entry_month': s['entry_month'],
            'entry_day': s['entry_day_type'], 'exit_month': s['exit_month'],
            'exit_day': s['exit_day_type'], 'initial_capital': float(s['initial_capital']),
            'year_start': s['year_start'], 'year_end': s['year_end']
        }
        cycles, metrics = run_backtest(conn, params)
        if cycles:
            print_results(params, cycles, metrics)
        conn.close()
        return

    if not args.ticker:
        print("Error: --ticker required (or --strategy-id)")
        return

    ticker = args.ticker.upper()

    if args.all_combinations:
        print(f"Running all entry/exit combinations for {ticker}...")
        count = 0
        best = None
        for entry_m in range(1, 13):
            for exit_m in range(1, 13):
                if entry_m == exit_m:
                    continue
                params = {
                    'ticker': ticker, 'entry_month': entry_m, 'entry_day': 'first',
                    'exit_month': exit_m, 'exit_day': 'last',
                    'initial_capital': args.capital,
                    'year_start': args.year_start, 'year_end': args.year_end
                }
                cycles, metrics = run_backtest(conn, params)
                if cycles and metrics:
                    save_to_db(conn, params, cycles, metrics)
                    count += 1
                    if best is None or metrics['cagr'] > best['cagr']:
                        best = {**metrics, 'entry_month': entry_m, 'exit_month': exit_m}

        print(f"\n{count} combinations saved.")
        if best:
            print(f"Best: M{best['entry_month']}->M{best['exit_month']} "
                  f"CAGR={best['cagr']:+.1f}% WR={best['win_rate']:.0f}%")
        conn.close()
        return

    if not args.entry_month or not args.exit_month:
        print("Error: --entry-month and --exit-month required (or --all-combinations)")
        return

    params = {
        'ticker': ticker, 'entry_month': args.entry_month,
        'entry_day': args.entry_day, 'exit_month': args.exit_month,
        'exit_day': args.exit_day, 'initial_capital': args.capital,
        'year_start': args.year_start, 'year_end': args.year_end
    }

    cycles, metrics = run_backtest(conn, params)
    if not cycles:
        print("No cycles could be computed. Check data availability.")
        conn.close()
        return

    strategy_id = save_to_db(conn, params, cycles, metrics)
    print_results(params, cycles, metrics)
    print(f"\nSaved as strategy_id: {strategy_id}")
    conn.close()


if __name__ == '__main__':
    main()
