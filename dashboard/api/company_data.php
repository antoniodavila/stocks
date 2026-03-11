<?php
require_once __DIR__ . '/_base.php';

$ticker = strtoupper(trim($_GET['ticker'] ?? ''));
if (empty($ticker)) json_error('Ticker required');

$pdo = get_db();

$stmt = $pdo->prepare("SELECT * FROM tickers WHERE ticker = ?");
$stmt->execute([$ticker]);
$company = $stmt->fetch();
if (!$company) json_error("Ticker {$ticker} not found", 404);

$stmt = $pdo->prepare("SELECT * FROM value_scores WHERE ticker = ? ORDER BY calculated_at DESC LIMIT 4");
$stmt->execute([$ticker]);
$scores = $stmt->fetchAll();

$stmt = $pdo->prepare("SELECT * FROM quality_ratios WHERE ticker = ? ORDER BY period DESC LIMIT 8");
$stmt->execute([$ticker]);
$quality_history = $stmt->fetchAll();

$stmt = $pdo->prepare("SELECT * FROM price_ratios WHERE ticker = ? ORDER BY date DESC LIMIT 8");
$stmt->execute([$ticker]);
$price_history = $stmt->fetchAll();

$stmt = $pdo->prepare("SELECT * FROM fundamentals WHERE ticker = ? AND period_type = 'Q' ORDER BY period DESC LIMIT 8");
$stmt->execute([$ticker]);
$fundamentals = $stmt->fetchAll();

$stmt = $pdo->prepare("SELECT * FROM ai_narratives WHERE ticker = ? AND (expires_at IS NULL OR expires_at > NOW()) ORDER BY generated_at DESC LIMIT 1");
$stmt->execute([$ticker]);
$narrative = $stmt->fetch();

$sector_etf_map = [
    'Technology' => 'XLK', 'Financials' => 'XLF', 'Health Care' => 'XLV',
    'Industrials' => 'XLI', 'Consumer Discretionary' => 'XLY',
    'Consumer Staples' => 'XLP', 'Materials' => 'XLB', 'Energy' => 'XLE',
    'Utilities' => 'XLU', 'Real Estate' => 'XLRE', 'Communication Services' => 'XLC',
];
$etf = $sector_etf_map[$company['sector']] ?? null;
$seasonality = [];
if ($etf) {
    $stmt = $pdo->prepare("SELECT * FROM seasonality_stats WHERE ticker = ? ORDER BY month");
    $stmt->execute([$etf]);
    $seasonality = $stmt->fetchAll();
}

json_response(compact('company', 'scores', 'quality_history', 'price_history',
    'fundamentals', 'narrative', 'seasonality', 'etf'));
