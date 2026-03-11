<?php
require_once __DIR__ . '/../config.php';
require_once __DIR__ . '/db.php';

$current_view = $_GET['view'] ?? 'heatmap';

// Last data update
try {
    $db = get_db();
    $stmt = $db->query("SELECT MAX(last_updated) as last_update FROM seasonality_stats");
    $last_update = $stmt->fetch()['last_update'] ?? 'Never';
} catch (Exception $e) {
    $last_update = 'DB Error';
}
?>
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Stock Analyzer - <?= ucfirst($current_view) ?></title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
    <link rel="stylesheet" href="<?= BASE_URL ?>/assets/css/style.css">
    <script src="https://cdn.jsdelivr.net/npm/jquery@3.7.1/dist/jquery.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.4/dist/chart.umd.min.js"></script>
</head>
<body>
<nav class="navbar navbar-expand-lg navbar-dark bg-dark">
    <div class="container-fluid">
        <a class="navbar-brand" href="<?= BASE_URL ?>/">Stock Analyzer</a>
        <button class="navbar-toggler" type="button" data-bs-toggle="collapse" data-bs-target="#navbarNav">
            <span class="navbar-toggler-icon"></span>
        </button>
        <div class="collapse navbar-collapse" id="navbarNav">
            <ul class="navbar-nav">
                <li class="nav-item">
                    <a class="nav-link <?= $current_view === 'heatmap' ? 'active' : '' ?>"
                       href="<?= BASE_URL ?>/?view=heatmap">Seasonality</a>
                </li>
                <li class="nav-item">
                    <a class="nav-link <?= $current_view === 'screener' ? 'active' : '' ?>"
                       href="<?= BASE_URL ?>/?view=screener">Value Screener</a>
                </li>
                <li class="nav-item">
                    <a class="nav-link <?= $current_view === 'backtest' ? 'active' : '' ?>"
                       href="<?= BASE_URL ?>/?view=backtest">Backtest</a>
                </li>
                <li class="nav-item">
                    <a class="nav-link <?= $current_view === 'signal' ? 'active' : '' ?>"
                       href="<?= BASE_URL ?>/?view=signal">Combined Signal</a>
                </li>
            </ul>
            <span class="navbar-text ms-auto small text-muted">
                Last update: <?= htmlspecialchars($last_update) ?>
            </span>
        </div>
    </div>
</nav>
<div class="container-fluid mt-3">
