<?php
require_once __DIR__ . '/_base.php';

$min_value_score = (float)($_GET['min_value_score'] ?? 70);
$min_winrate     = (float)($_GET['min_winrate'] ?? 65);
$min_backtest_wr = (float)($_GET['min_backtest_wr'] ?? 60);
$target_month    = (int)($_GET['month'] ?? date('n'));

$pdo = get_db();

$sector_etf_case = "
    CASE t.sector
        WHEN 'Technology' THEN 'XLK'
        WHEN 'Financials' THEN 'XLF'
        WHEN 'Health Care' THEN 'XLV'
        WHEN 'Industrials' THEN 'XLI'
        WHEN 'Consumer Discretionary' THEN 'XLY'
        WHEN 'Consumer Staples' THEN 'XLP'
        WHEN 'Materials' THEN 'XLB'
        WHEN 'Energy' THEN 'XLE'
        WHEN 'Utilities' THEN 'XLU'
        WHEN 'Real Estate' THEN 'XLRE'
        WHEN 'Communication Services' THEN 'XLC'
    END
";

$stmt = $pdo->prepare("
    SELECT
        t.ticker, t.name, t.sector,
        vs.total_score, vs.quality_score, vs.sector_percentile, vs.quality_trend,
        ss.avg_return AS sector_avg_return, ss.win_rate AS sector_win_rate,
        br.win_rate AS backtest_win_rate, br.cagr AS backtest_cagr,
        br.sharpe_ratio, s.entry_month, s.exit_month,
        $sector_etf_case AS sector_etf
    FROM tickers t
    JOIN value_scores vs ON t.ticker = vs.ticker
        AND vs.calculated_at = (SELECT MAX(calculated_at) FROM value_scores WHERE ticker = t.ticker)
        AND vs.total_score >= ?
    JOIN seasonality_stats ss ON ss.ticker = ($sector_etf_case)
        AND ss.month = ? AND ss.win_rate >= ? AND ss.avg_return > 0
    JOIN strategies s ON s.ticker = ss.ticker AND s.entry_month = ?
    JOIN backtest_results br ON br.strategy_id = s.id
        AND br.win_rate >= ? AND br.cagr > 0
    WHERE t.sp500 = TRUE
    ORDER BY vs.total_score DESC, ss.win_rate DESC
    LIMIT 50
");
$stmt->execute([$min_value_score, $target_month, $min_winrate, $target_month, $min_backtest_wr]);
$signals = $stmt->fetchAll();

// Upcoming favorable months
$upcoming = [];
$current = (int)date('n');
for ($i = 0; $i < 3; $i++) {
    $m = (($current + $i - 1) % 12) + 1;
    $stmt2 = $pdo->prepare("
        SELECT ticker, avg_return, win_rate FROM seasonality_stats
        WHERE month = ? AND win_rate >= ? AND avg_return > 0
        ORDER BY win_rate DESC
    ");
    $stmt2->execute([$m, $min_winrate]);
    $upcoming[] = [
        'month' => $m,
        'month_name' => date('F', mktime(0, 0, 0, $m, 1)),
        'sectors' => $stmt2->fetchAll(),
    ];
}

json_response([
    'month'       => $target_month,
    'month_name'  => date('F', mktime(0, 0, 0, $target_month, 1)),
    'signals'     => $signals,
    'total'       => count($signals),
    'thresholds'  => compact('min_value_score', 'min_winrate', 'min_backtest_wr'),
    'next_months' => $upcoming,
]);
