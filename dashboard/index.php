<?php
$start_time = microtime(true);
require_once __DIR__ . '/config.php';

// Auth simple por token (si DASHBOARD_TOKEN no está vacío)
if (!empty(DASHBOARD_TOKEN)) {
    $token = $_GET['token'] ?? $_COOKIE['dash_token'] ?? '';
    if ($token === DASHBOARD_TOKEN) {
        setcookie('dash_token', $token, time() + 86400 * 30, '/');
    } elseif (empty($token)) {
        include VIEWS_PATH . 'login.php';
        exit;
    }
}

$view = $_GET['view'] ?? 'heatmap';
$allowed_views = ['heatmap', 'screener', 'backtest', 'signal', 'company'];
if (!in_array($view, $allowed_views)) {
    $view = 'heatmap';
}

include __DIR__ . '/includes/header.php';
include VIEWS_PATH . $view . '.php';
include __DIR__ . '/includes/footer.php';
