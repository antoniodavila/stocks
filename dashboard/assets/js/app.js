// Global utilities for Stock Analyzer Dashboard

const API_BASE = '/stocks/dashboard/api';

function fetchAPI(endpoint, params = {}) {
    const url = new URL(API_BASE + '/' + endpoint, window.location.origin);
    Object.entries(params).forEach(([k, v]) => {
        if (v !== '' && v !== null && v !== undefined) url.searchParams.set(k, v);
    });
    return $.getJSON(url.toString());
}

function formatPct(val, decimals = 2) {
    if (val === null || val === undefined) return '—';
    const num = parseFloat(val);
    const sign = num >= 0 ? '+' : '';
    return sign + num.toFixed(decimals) + '%';
}

function formatNum(val, decimals = 0) {
    if (val === null || val === undefined) return '—';
    return parseFloat(val).toLocaleString('en-US', { minimumFractionDigits: decimals, maximumFractionDigits: decimals });
}

function scoreClass(score) {
    if (score === null || score === undefined) return '';
    score = parseFloat(score);
    if (score >= 70) return 'score-high';
    if (score >= 40) return 'score-mid';
    return 'score-low';
}

// Make table columns sortable
function initSortable(tableId) {
    $(`#${tableId} th.sortable`).on('click', function() {
        const table = $(this).closest('table');
        const idx = $(this).index();
        const rows = table.find('tbody tr').get();
        const isAsc = $(this).hasClass('sort-asc');

        rows.sort((a, b) => {
            const aVal = parseFloat($(a).children('td').eq(idx).text().replace(/[^0-9.-]/g, '')) || 0;
            const bVal = parseFloat($(b).children('td').eq(idx).text().replace(/[^0-9.-]/g, '')) || 0;
            return isAsc ? aVal - bVal : bVal - aVal;
        });

        table.find('th.sortable').removeClass('sort-asc sort-desc');
        $(this).addClass(isAsc ? 'sort-desc' : 'sort-asc');
        table.find('tbody').empty().append(rows);
    });
}
