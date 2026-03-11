#!/usr/bin/env python3
"""
M2-1: Score Calculator — Quality-First Value, percentiles por sector.
Pobla tabla: value_scores.

Uso:
  python scripts/analyzers/score_calculator.py
  python scripts/analyzers/score_calculator.py --ticker AAPL
  python scripts/analyzers/score_calculator.py --sector Technology
"""

import argparse
import sys
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import get_db_connection

WEIGHTS = {
    'quality':   0.35,
    'valuation': 0.30,
    'solidity':  0.20,
    'growth':    0.15,
}


def normalize_to_percentile(series: pd.Series, higher_is_better: bool = True) -> pd.Series:
    """Convierte valores a percentiles 0-100 dentro del grupo."""
    if series.isna().all():
        return series
    ranks = series.rank(pct=True, na_option='bottom')
    if not higher_is_better:
        ranks = 1 - ranks
    return ranks * 100


def load_data(conn, ticker_filter=None, sector_filter=None) -> pd.DataFrame:
    """Carga datos más recientes por ticker desde quality_ratios + price_ratios + fundamentals."""
    cursor = conn.cursor(dictionary=True)

    query = """
        SELECT t.ticker, t.sector,
               qr.roe, qr.roic, qr.gross_margin, qr.operating_margin,
               qr.debt_equity, qr.current_ratio, qr.interest_coverage,
               pr.pe_ratio, pr.pb_ratio, pr.pfcf_ratio, pr.ev_ebitda
        FROM tickers t
        INNER JOIN quality_ratios qr ON t.ticker = qr.ticker
            AND qr.period = (SELECT MAX(period) FROM quality_ratios WHERE ticker = t.ticker)
        LEFT JOIN price_ratios pr ON t.ticker = pr.ticker
            AND pr.date = (SELECT MAX(date) FROM price_ratios WHERE ticker = t.ticker)
        WHERE t.sp500 = TRUE AND t.active = TRUE
    """
    params = []
    if ticker_filter:
        query += " AND t.ticker = %s"
        params.append(ticker_filter)
    if sector_filter:
        query += " AND t.sector = %s"
        params.append(sector_filter)

    cursor.execute(query, params)
    rows = cursor.fetchall()
    cursor.close()

    if not rows:
        return pd.DataFrame()

    return pd.DataFrame(rows)


def calc_growth(conn, ticker: str) -> dict:
    """Calcula EPS growth y Revenue growth (5 años)."""
    cursor = conn.cursor(dictionary=True)

    # EPS actual y hace 5 años (~20 trimestres)
    cursor.execute("""
        SELECT period, eps_diluted, revenue
        FROM fundamentals
        WHERE ticker = %s AND period_type = 'Q' AND eps_diluted IS NOT NULL
        ORDER BY period DESC
    """, (ticker,))
    rows = cursor.fetchall()
    cursor.close()

    result = {'eps_growth_5y': None, 'revenue_growth': None}
    if len(rows) < 4:
        return result

    current = rows[0]
    # Buscar hace ~20 trimestres
    old_idx = min(19, len(rows) - 1)
    old = rows[old_idx]

    # EPS Growth CAGR
    if current['eps_diluted'] and old['eps_diluted'] and float(old['eps_diluted']) > 0:
        years = old_idx / 4
        if years > 0:
            ratio = float(current['eps_diluted']) / float(old['eps_diluted'])
            if ratio > 0:
                result['eps_growth_5y'] = (ratio ** (1 / years) - 1) * 100

    # Revenue Growth
    if current['revenue'] and old['revenue'] and int(old['revenue']) > 0:
        years = old_idx / 4
        if years > 0:
            ratio = int(current['revenue']) / int(old['revenue'])
            if ratio > 0:
                result['revenue_growth'] = (ratio ** (1 / years) - 1) * 100

    return result


def calc_quality_trend(conn, ticker: str) -> int:
    """Compara ROE actual vs hace 4 trimestres. Retorna -1, 0, o 1."""
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT period, roe FROM quality_ratios
        WHERE ticker = %s AND roe IS NOT NULL
        ORDER BY period DESC LIMIT 5
    """, (ticker,))
    rows = cursor.fetchall()
    cursor.close()

    if len(rows) < 2:
        return 0

    current_roe = float(rows[0]['roe'])
    old_idx = min(3, len(rows) - 1)
    old_roe = float(rows[old_idx]['roe'])

    diff = (current_roe - old_roe) * 100  # convert to percentage points
    if diff > 2:
        return 1   # improving
    elif diff < -2:
        return -1  # deteriorating
    return 0       # stable


def calculate_scores(df: pd.DataFrame) -> pd.DataFrame:
    """Calcula sub-scores y total_score por sector percentiles."""
    results = []

    for sector, group in df.groupby('sector'):
        g = group.copy()

        # Quality percentiles
        g['roe_pct'] = normalize_to_percentile(g['roe'])
        g['roic_pct'] = normalize_to_percentile(g['roic'])
        g['gm_pct'] = normalize_to_percentile(g['gross_margin'])

        # Valuation percentiles (lower is better)
        g['pfcf_pct'] = normalize_to_percentile(g['pfcf_ratio'], higher_is_better=False)
        g['ev_ebitda_pct'] = normalize_to_percentile(g['ev_ebitda'], higher_is_better=False)
        g['pe_pct'] = normalize_to_percentile(g['pe_ratio'], higher_is_better=False)
        g['pb_pct'] = normalize_to_percentile(g['pb_ratio'], higher_is_better=False)

        # Solidity percentiles
        g['de_pct'] = normalize_to_percentile(g['debt_equity'], higher_is_better=False)
        g['cr_pct'] = normalize_to_percentile(g['current_ratio'])
        g['ic_pct'] = normalize_to_percentile(g['interest_coverage'])

        # Growth percentiles
        g['eps_g_pct'] = normalize_to_percentile(g['eps_growth_5y'])
        g['rev_g_pct'] = normalize_to_percentile(g['revenue_growth'])

        # Sub-scores
        g['quality_score'] = (g['roe_pct'] + g['roic_pct'] + g['gm_pct']) / 3
        g['valuation_score'] = (g['pfcf_pct'] * 2 + g['ev_ebitda_pct'] + g['pe_pct'] + g['pb_pct']) / 5
        g['solidity_score'] = (g['de_pct'] + g['cr_pct'] + g['ic_pct']) / 3
        g['growth_score'] = (g['eps_g_pct'] + g['rev_g_pct']) / 2

        # Total score
        g['total_score'] = (
            g['quality_score'] * WEIGHTS['quality'] +
            g['valuation_score'] * WEIGHTS['valuation'] +
            g['solidity_score'] * WEIGHTS['solidity'] +
            g['growth_score'] * WEIGHTS['growth']
        )

        # Apply trend adjustment
        g['total_score'] = g['total_score'] + g['quality_trend'] * 5

        # Clamp 0-100
        g['total_score'] = g['total_score'].clip(0, 100)

        # Sector percentile of total_score
        g['sector_percentile'] = normalize_to_percentile(g['total_score'])

        results.append(g)

    if not results:
        return pd.DataFrame()
    return pd.concat(results, ignore_index=True)


def save_scores(conn, df: pd.DataFrame):
    """Inserta resultados en value_scores."""
    cursor = conn.cursor()
    today = date.today().isoformat()

    sql = """
        INSERT INTO value_scores
            (ticker, calculated_at, total_score, quality_score, valuation_score,
             solidity_score, growth_score, sector_percentile, quality_trend)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE
            total_score = VALUES(total_score),
            quality_score = VALUES(quality_score),
            valuation_score = VALUES(valuation_score),
            solidity_score = VALUES(solidity_score),
            growth_score = VALUES(growth_score),
            sector_percentile = VALUES(sector_percentile),
            quality_trend = VALUES(quality_trend)
    """

    for _, row in df.iterrows():
        cursor.execute(sql, (
            row['ticker'], today,
            round(row['total_score'], 2) if pd.notna(row['total_score']) else None,
            round(row['quality_score'], 2) if pd.notna(row['quality_score']) else None,
            round(row['valuation_score'], 2) if pd.notna(row['valuation_score']) else None,
            round(row['solidity_score'], 2) if pd.notna(row['solidity_score']) else None,
            round(row['growth_score'], 2) if pd.notna(row['growth_score']) else None,
            round(row['sector_percentile'], 2) if pd.notna(row['sector_percentile']) else None,
            int(row['quality_trend']),
        ))

    conn.commit()
    cursor.close()


def main():
    parser = argparse.ArgumentParser(description='Quality-First Value Score Calculator')
    parser.add_argument('--ticker', type=str, help='Calculate for single ticker')
    parser.add_argument('--sector', type=str, help='Calculate for single sector')
    args = parser.parse_args()

    conn = get_db_connection()

    # Load base data
    print("Loading data from quality_ratios + price_ratios...")
    df = load_data(conn, args.ticker, args.sector)

    if df.empty:
        print("No data found. Run load_fundamentals.py first.")
        conn.close()
        return

    print(f"Tickers loaded: {len(df)}")
    print(f"Sectors: {df['sector'].nunique()}")

    # Add growth metrics
    print("Calculating growth metrics...")
    growth_data = []
    for ticker in df['ticker']:
        g = calc_growth(conn, ticker)
        g['ticker'] = ticker
        g['quality_trend'] = calc_quality_trend(conn, ticker)
        growth_data.append(g)

    growth_df = pd.DataFrame(growth_data)
    df = df.merge(growth_df, on='ticker', how='left')
    df['eps_growth_5y'] = df['eps_growth_5y'].fillna(0)
    df['revenue_growth'] = df['revenue_growth'].fillna(0)
    df['quality_trend'] = df['quality_trend'].fillna(0).astype(int)

    # Calculate scores
    print("Calculating scores by sector percentiles...")
    scored = calculate_scores(df)

    if scored.empty:
        print("No scores calculated.")
        conn.close()
        return

    # Save to DB
    save_scores(conn, scored)

    # Print summary
    print(f"\n=== Score Calculator ===")
    print(f"Tickers processed: {len(scored)}")
    print(f"Sectors: {scored['sector'].nunique()}")

    if len(scored) > 1:
        bins = [(90, 100), (70, 89), (40, 69), (0, 39)]
        labels = ['Top decile (90-100)', 'High (70-89)', 'Mid (40-69)', 'Low (<40)']
        print("\nScore distribution:")
        for (lo, hi), label in zip(bins, labels):
            count = len(scored[(scored['total_score'] >= lo) & (scored['total_score'] <= hi)])
            print(f"  {label}: {count:>4} companies")

        print(f"\nTop 10 by total_score:")
        top10 = scored.nlargest(10, 'total_score')
        for i, (_, row) in enumerate(top10.iterrows(), 1):
            print(f"  {i:>2}. {row['ticker']:<6} - {row['sector']:<25} - {row['total_score']:.1f}")

    elif args.ticker:
        row = scored.iloc[0]
        print(f"\n  Ticker: {row['ticker']}")
        print(f"  Sector: {row['sector']}")
        print(f"  Total Score:      {row['total_score']:.1f}")
        print(f"  Quality Score:    {row['quality_score']:.1f} (weight: 35%)")
        print(f"  Valuation Score:  {row['valuation_score']:.1f} (weight: 30%)")
        print(f"  Solidity Score:   {row['solidity_score']:.1f} (weight: 20%)")
        print(f"  Growth Score:     {row['growth_score']:.1f} (weight: 15%)")
        print(f"  Quality Trend:    {row['quality_trend']}")
        print(f"  Sector Percentile: {row['sector_percentile']:.1f}")

    print(f"\nSaved to value_scores: {len(scored)} rows")
    conn.close()


if __name__ == '__main__':
    main()
