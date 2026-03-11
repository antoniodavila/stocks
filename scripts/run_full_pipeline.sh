#!/bin/bash
# Full data pipeline: prices -> fundamentals -> scores -> backtests
# Run from project root: bash scripts/run_full_pipeline.sh

set -e
cd "$(dirname "$0")/.."
source scripts/venv/bin/activate

echo "=== [1/4] Loading S&P 500 prices ==="
python scripts/data_loaders/load_prices.py --resume --batch 20 --sleep 2

echo ""
echo "=== [2/4] Loading fundamentals (EDGAR) ==="
python scripts/data_loaders/load_fundamentals.py --resume

echo ""
echo "=== [3/4] Calculating Value Scores ==="
python scripts/analyzers/score_calculator.py

echo ""
echo "=== [4/4] Running all backtest combinations ==="
python scripts/analyzers/backtest_engine.py --all-combinations

echo ""
echo "=== Pipeline complete! ==="
python -c "
import sys; sys.path.insert(0, 'scripts')
from config import get_db_connection
conn = get_db_connection()
cur = conn.cursor()
tables = ['tickers','stock_prices','monthly_returns','fundamentals','quality_ratios','price_ratios','value_scores','seasonality_stats','backtest_results']
for t in tables:
    cur.execute(f'SELECT COUNT(*) FROM {t}')
    print(f'  {t}: {cur.fetchone()[0]} rows')
conn.close()
"
