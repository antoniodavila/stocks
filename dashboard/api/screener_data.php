<?php
require_once __DIR__ . '/_base.php';

$sector    = $_GET['sector'] ?? '';
$min_score = (float)($_GET['min_score'] ?? 0);
$sort_by   = $_GET['sort_by'] ?? 'total_score';
$sort_dir  = strtoupper($_GET['sort_dir'] ?? 'DESC') === 'ASC' ? 'ASC' : 'DESC';
$limit     = min((int)($_GET['limit'] ?? 100), 500);
$offset    = (int)($_GET['offset'] ?? 0);

$allowed_sorts = ['total_score','quality_score','valuation_score','solidity_score',
                  'growth_score','sector_percentile','pe_ratio','roe','roic','ticker'];
if (!in_array($sort_by, $allowed_sorts)) $sort_by = 'total_score';

$pdo = get_db();

$where = ["vs.total_score >= ?", "t.sp500 = TRUE"];
$params = [$min_score];

if (!empty($sector)) {
    $where[] = "t.sector = ?";
    $params[] = $sector;
}

$where_sql = 'WHERE ' . implode(' AND ', $where);

$stmt = $pdo->prepare("
    SELECT
        t.ticker, t.name, t.sector, t.industry,
        vs.total_score, vs.quality_score, vs.valuation_score,
        vs.solidity_score, vs.growth_score, vs.sector_percentile,
        vs.quality_trend, vs.calculated_at,
        qr.roe, qr.roic, qr.gross_margin, qr.debt_equity, qr.current_ratio,
        pr.pe_ratio, pr.pb_ratio, pr.pfcf_ratio, pr.ev_ebitda,
        t.market_cap
    FROM tickers t
    JOIN value_scores vs ON t.ticker = vs.ticker
        AND vs.calculated_at = (SELECT MAX(calculated_at) FROM value_scores WHERE ticker = t.ticker)
    LEFT JOIN quality_ratios qr ON t.ticker = qr.ticker
        AND qr.period = (SELECT MAX(period) FROM quality_ratios WHERE ticker = t.ticker)
    LEFT JOIN price_ratios pr ON t.ticker = pr.ticker
        AND pr.date = (SELECT MAX(date) FROM price_ratios WHERE ticker = t.ticker)
    $where_sql
    ORDER BY $sort_by $sort_dir
    LIMIT ? OFFSET ?
");
$params[] = $limit;
$params[] = $offset;
$stmt->execute($params);
$companies = $stmt->fetchAll();

$count_params = array_slice($params, 0, -2);
$count_stmt = $pdo->prepare("
    SELECT COUNT(*) FROM tickers t
    JOIN value_scores vs ON t.ticker = vs.ticker
        AND vs.calculated_at = (SELECT MAX(calculated_at) FROM value_scores WHERE ticker = t.ticker)
    $where_sql
");
$count_stmt->execute($count_params);
$total = $count_stmt->fetchColumn();

$sectors = $pdo->query("SELECT DISTINCT sector FROM tickers WHERE sp500=TRUE AND sector IS NOT NULL ORDER BY sector")->fetchAll(PDO::FETCH_COLUMN);

json_response([
    'companies' => $companies,
    'total'     => (int)$total,
    'sectors'   => $sectors,
    'filters'   => compact('sector', 'min_score', 'sort_by', 'sort_dir'),
]);
