<h2>Seasonality Heatmap — S&P 500 Sector ETFs</h2>

<div class="filter-bar d-flex align-items-center gap-3 flex-wrap">
    <div>
        <label class="form-label mb-0 small">Metric:</label>
        <div class="btn-group btn-group-sm">
            <input type="radio" class="btn-check" name="metric" id="m-return" value="avg_return" checked>
            <label class="btn btn-outline-primary" for="m-return">Avg Return</label>
            <input type="radio" class="btn-check" name="metric" id="m-winrate" value="win_rate">
            <label class="btn btn-outline-primary" for="m-winrate">Win Rate</label>
        </div>
    </div>
    <div>
        <label class="form-label mb-0 small">Min Win Rate:</label>
        <input type="number" id="min_winrate" class="form-control form-control-sm" value="0" min="0" max="100" step="5" style="width:80px">
    </div>
    <button id="btn-update" class="btn btn-sm btn-primary">Update</button>
</div>

<div class="table-responsive">
    <table class="table table-bordered table-sm text-center" id="heatmap-table">
        <thead class="table-dark"><tr><th>ETF</th></tr></thead>
        <tbody></tbody>
    </table>
</div>

<h5 class="mt-4">Top 20 Cells by Win Rate</h5>
<table class="table table-sm table-striped" id="ranking-table">
    <thead><tr><th>ETF</th><th>Month</th><th>Avg Return</th><th>Win Rate</th><th>Years</th></tr></thead>
    <tbody></tbody>
</table>

<script>
const MONTHS = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];

function getColor(value, metric) {
    if (metric === 'avg_return') {
        if (value > 3)  return '#1a7a3f';
        if (value > 1)  return '#52b788';
        if (value > -1) return '#f8f9fa';
        if (value > -3) return '#e07070';
        return '#c00000';
    } else {
        if (value > 75) return '#1a7a3f';
        if (value > 65) return '#52b788';
        if (value > 50) return '#f8f9fa';
        if (value > 35) return '#e07070';
        return '#c00000';
    }
}

function textColor(bg) {
    return (bg === '#1a7a3f' || bg === '#c00000') ? '#fff' : '#333';
}

function loadHeatmap() {
    const metric = $('input[name="metric"]:checked').val();
    const minWr = $('#min_winrate').val();

    fetchAPI('heatmap_data.php', {metric: metric, min_winrate: minWr}).done(function(resp) {
        // Header
        let header = '<tr><th class="table-dark">ETF</th>';
        MONTHS.forEach(m => header += `<th class="table-dark">${m}</th>`);
        header += '</tr>';
        $('#heatmap-table thead').html(header);

        // Body
        let body = '';
        let allCells = [];
        resp.etf_order.forEach(etf => {
            body += `<tr><td class="fw-bold">${etf}</td>`;
            for (let m = 1; m <= 12; m++) {
                const cell = (resp.data[etf] || {})[m];
                if (!cell) {
                    body += '<td style="background:#eee">—</td>';
                    continue;
                }
                const val = cell[metric];
                const bg = getColor(val, metric);
                const display = metric === 'avg_return' ? val.toFixed(1) + '%' : val.toFixed(0) + '%';
                const tip = `${etf} — ${MONTHS[m-1]}\navg: ${cell.avg_return.toFixed(2)}%\nwin: ${cell.win_rate.toFixed(0)}%\nbest: ${cell.best_return.toFixed(2)}%\nworst: ${cell.worst_return.toFixed(2)}%\nyears: ${cell.years_analyzed}`;
                body += `<td style="background:${bg};color:${textColor(bg)}" title="${tip}">${display}</td>`;
                allCells.push({etf, month: m, ...cell});
            }
            body += '</tr>';
        });
        $('#heatmap-table tbody').html(body);

        // Ranking
        allCells.sort((a, b) => b.win_rate - a.win_rate);
        let rank = '';
        allCells.slice(0, 20).forEach(c => {
            rank += `<tr><td>${c.etf}</td><td>${MONTHS[c.month-1]}</td>` +
                    `<td>${formatPct(c.avg_return)}</td><td>${c.win_rate.toFixed(0)}%</td>` +
                    `<td>${c.years_analyzed}</td></tr>`;
        });
        $('#ranking-table tbody').html(rank);
    });
}

$(document).ready(function() {
    loadHeatmap();
    $('#btn-update').click(loadHeatmap);
    $('input[name="metric"]').change(loadHeatmap);
});
</script>
