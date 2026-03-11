<?php
require_once __DIR__ . '/_base.php';

$action = $_GET['action'] ?? 'run';

if ($action === 'list') {
    $pdo = get_db();
    $stmt = $pdo->query("
        SELECT s.*, br.cagr, br.win_rate AS result_wr, br.total_return, br.sharpe_ratio
        FROM strategies s
        LEFT JOIN backtest_results br ON s.id = br.strategy_id
        ORDER BY s.created_at DESC LIMIT 50
    ");
    json_response(['strategies' => $stmt->fetchAll()]);
}

if ($action === 'load') {
    $id = (int)($_GET['id'] ?? 0);
    if (!$id) json_error('Strategy ID required');
    $pdo = get_db();
    $strategy = $pdo->prepare("SELECT * FROM strategies WHERE id = ?");
    $strategy->execute([$id]);
    $s = $strategy->fetch();
    if (!$s) json_error('Strategy not found', 404);

    $results = $pdo->prepare("SELECT * FROM backtest_results WHERE strategy_id = ?");
    $results->execute([$id]);
    $cycles = $pdo->prepare("SELECT * FROM backtest_cycles WHERE strategy_id = ? ORDER BY year");
    $cycles->execute([$id]);

    json_response([
        'strategy' => $s,
        'metrics'  => $results->fetch(),
        'cycles'   => $cycles->fetchAll(),
    ]);
}

// Run backtest
$ticker      = strtoupper(trim($_GET['ticker'] ?? ''));
$entry_month = (int)($_GET['entry_month'] ?? 0);
$entry_day   = $_GET['entry_day'] ?? 'first';
$exit_month  = (int)($_GET['exit_month'] ?? 0);
$exit_day    = $_GET['exit_day'] ?? 'last';
$capital     = (float)($_GET['capital'] ?? 10000);
$year_start  = (int)($_GET['year_start'] ?? 2010);
$year_end    = (int)($_GET['year_end'] ?? 2024);

if (empty($ticker) || $entry_month < 1 || $entry_month > 12 || $exit_month < 1 || $exit_month > 12) {
    json_error('Invalid parameters');
}
if (!in_array($entry_day, ['first', 'last']) || !in_array($exit_day, ['first', 'last'])) {
    json_error('Invalid day type');
}

$pdo = get_db();

$check = $pdo->prepare("SELECT ticker FROM tickers WHERE ticker = ? LIMIT 1");
$check->execute([$ticker]);
if (!$check->fetch()) json_error("Ticker {$ticker} not found");

// Run backtest in PHP
function get_trading_day(PDO $pdo, string $ticker, int $year, int $month, string $type): ?array {
    $order = $type === 'first' ? 'ASC' : 'DESC';
    $stmt = $pdo->prepare("
        SELECT date, adj_close FROM stock_prices
        WHERE ticker = ? AND YEAR(date) = ? AND MONTH(date) = ?
        ORDER BY date $order LIMIT 1
    ");
    $stmt->execute([$ticker, $year, $month]);
    return $stmt->fetch() ?: null;
}

$cycles = [];
$running_capital = $capital;

for ($year = $year_start; $year <= $year_end; $year++) {
    $exit_year = ($exit_month <= $entry_month) ? $year + 1 : $year;

    $entry = get_trading_day($pdo, $ticker, $year, $entry_month, $entry_day);
    $exit  = get_trading_day($pdo, $ticker, $exit_year, $exit_month, $exit_day);

    if (!$entry || !$exit || !$entry['adj_close'] || !$exit['adj_close']) continue;

    $ep = (float)$entry['adj_close'];
    $xp = (float)$exit['adj_close'];
    $ret = ($xp - $ep) / $ep * 100;
    $cap_start = $running_capital;
    $running_capital *= (1 + $ret / 100);

    // Buy & hold for same period
    $bh_ret = $ret; // same ticker same dates

    $cycles[] = [
        'year'          => $year,
        'entry_date'    => $entry['date'],
        'exit_date'     => $exit['date'],
        'entry_price'   => round($ep, 4),
        'exit_price'    => round($xp, 4),
        'return_pct'    => round($ret, 4),
        'capital_start' => round($cap_start, 2),
        'capital_end'   => round($running_capital, 2),
        'buyhold_return'=> round($bh_ret, 4),
    ];
}

if (empty($cycles)) json_error('No cycles computed. Check data availability.');

// Metrics
$returns = array_column($cycles, 'return_pct');
$final = end($cycles)['capital_end'];
$n = count($cycles);
$cagr = $n > 0 ? (pow($final / $capital, 1 / $n) - 1) * 100 : 0;
$wins = count(array_filter($returns, fn($r) => $r > 0));
$wr = $n > 0 ? $wins / $n * 100 : 0;

$peak = $capital;
$max_dd = 0;
foreach ($cycles as $c) {
    if ($c['capital_end'] > $peak) $peak = $c['capital_end'];
    $dd = ($peak - $c['capital_end']) / $peak * 100;
    if ($dd > $max_dd) $max_dd = $dd;
}

$avg_ret = array_sum($returns) / $n;
$std = 0;
foreach ($returns as $r) $std += pow($r - $avg_ret, 2);
$std = sqrt($std / max($n - 1, 1));
$sharpe = $std > 0 ? ($avg_ret - 2) / $std : 0;

$metrics = [
    'total_return'     => round(($final - $capital) / $capital * 100, 4),
    'cagr'             => round($cagr, 4),
    'win_rate'         => round($wr, 2),
    'avg_cycle_return' => round($avg_ret, 4),
    'best_year_return' => round(max($returns), 4),
    'worst_year_return'=> round(min($returns), 4),
    'max_drawdown'     => round($max_dd, 4),
    'sharpe_ratio'     => round($sharpe, 4),
    'total_cycles'     => $n,
    'winning_cycles'   => $wins,
];

// Save
$stmt = $pdo->prepare("
    INSERT INTO strategies (ticker, entry_month, entry_day_type, exit_month, exit_day_type,
        initial_capital, year_start, year_end, name)
    VALUES (?,?,?,?,?,?,?,?,?)
");
$stmt->execute([$ticker, $entry_month, $entry_day, $exit_month, $exit_day,
    $capital, $year_start, $year_end, "$ticker M$entry_month-M$exit_month"]);
$sid = $pdo->lastInsertId();

$stmt = $pdo->prepare("
    INSERT INTO backtest_results (strategy_id, total_return, cagr, win_rate, avg_cycle_return,
        best_year_return, worst_year_return, max_drawdown, sharpe_ratio, total_cycles, winning_cycles)
    VALUES (?,?,?,?,?,?,?,?,?,?,?)
");
$stmt->execute([$sid, $metrics['total_return'], $metrics['cagr'], $metrics['win_rate'],
    $metrics['avg_cycle_return'], $metrics['best_year_return'], $metrics['worst_year_return'],
    $metrics['max_drawdown'], $metrics['sharpe_ratio'], $n, $wins]);

$stmt = $pdo->prepare("
    INSERT INTO backtest_cycles (strategy_id, year, entry_date, exit_date, entry_price,
        exit_price, return_pct, capital_start, capital_end, buyhold_return)
    VALUES (?,?,?,?,?,?,?,?,?,?)
");
foreach ($cycles as $c) {
    $stmt->execute([$sid, $c['year'], $c['entry_date'], $c['exit_date'], $c['entry_price'],
        $c['exit_price'], $c['return_pct'], $c['capital_start'], $c['capital_end'], $c['buyhold_return']]);
}

json_response([
    'strategy_id' => (int)$sid,
    'metrics'     => $metrics,
    'cycles'      => $cycles,
]);
