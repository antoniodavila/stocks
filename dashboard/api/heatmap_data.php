<?php
require_once __DIR__ . '/_base.php';

$metric = $_GET['metric'] ?? 'avg_return';
$min_winrate = (float)($_GET['min_winrate'] ?? 0);

if (!in_array($metric, ['avg_return', 'win_rate'])) {
    json_error('Invalid metric');
}

$pdo = get_db();
$stmt = $pdo->prepare("
    SELECT ticker, month, avg_return, win_rate, best_return, worst_return, years_analyzed
    FROM seasonality_stats
    WHERE win_rate >= ?
    ORDER BY ticker, month
");
$stmt->execute([$min_winrate]);

$data = [];
foreach ($stmt->fetchAll() as $row) {
    $data[$row['ticker']][$row['month']] = [
        'avg_return'     => (float)$row['avg_return'],
        'win_rate'       => (float)$row['win_rate'],
        'best_return'    => (float)$row['best_return'],
        'worst_return'   => (float)$row['worst_return'],
        'years_analyzed' => (int)$row['years_analyzed'],
    ];
}

$etf_order = ['XLK','XLF','XLV','XLI','XLY','XLP','XLB','XLE','XLU','XLRE','XLC'];
$month_names = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];

json_response([
    'metric'      => $metric,
    'min_winrate' => $min_winrate,
    'etf_order'   => $etf_order,
    'month_names' => $month_names,
    'data'        => $data,
]);
