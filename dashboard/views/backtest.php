<h2>Backtest Engine</h2>
<div class="view-description mb-3">
    <p>Test <strong>seasonal trading strategies</strong> against historical data. Enter a month to buy and a month to sell, and see how the strategy would have performed over the last 15 years.</p>
    <details>
        <summary>How to use this</summary>
        <ul>
            <li><strong>Ticker</strong> — Any ETF or stock in the database (e.g., XLK, AAPL, XLF).</li>
            <li><strong>Entry/Exit Month</strong> — The months to buy and sell. E.g., "Buy Nov, Sell Apr" tests the classic winter rally.</li>
            <li><strong>Entry/Exit Day</strong> — First or last trading day of the month.</li>
            <li><strong>Results</strong> include: total return, CAGR, win rate, max drawdown, Sharpe ratio, and a year-by-year breakdown.</li>
            <li>Strategies are <strong>saved automatically</strong> and appear in the sidebar for quick reload.</li>
            <li>Tip: Use the <em>Heatmap</em> to identify strong seasonal windows, then backtest them here.</li>
        </ul>
    </details>
</div>

<div class="row">
    <div class="col-md-4">
        <div class="card">
            <div class="card-body">
                <h5 class="card-title">Strategy Parameters</h5>
                <div class="mb-2">
                    <label class="form-label small">Ticker</label>
                    <input type="text" id="bt-ticker" class="form-control form-control-sm" value="XLK" placeholder="e.g. XLK, AAPL">
                </div>
                <div class="row mb-2">
                    <div class="col-6">
                        <label class="form-label small">Entry Month</label>
                        <select id="bt-entry-month" class="form-select form-select-sm"></select>
                    </div>
                    <div class="col-6">
                        <label class="form-label small">Entry Day</label>
                        <select id="bt-entry-day" class="form-select form-select-sm">
                            <option value="first">First</option>
                            <option value="last">Last</option>
                        </select>
                    </div>
                </div>
                <div class="row mb-2">
                    <div class="col-6">
                        <label class="form-label small">Exit Month</label>
                        <select id="bt-exit-month" class="form-select form-select-sm"></select>
                    </div>
                    <div class="col-6">
                        <label class="form-label small">Exit Day</label>
                        <select id="bt-exit-day" class="form-select form-select-sm">
                            <option value="first">First</option>
                            <option value="last" selected>Last</option>
                        </select>
                    </div>
                </div>
                <div class="mb-2">
                    <label class="form-label small">Capital ($)</label>
                    <input type="number" id="bt-capital" class="form-control form-control-sm" value="10000">
                </div>
                <div class="row mb-3">
                    <div class="col-6">
                        <label class="form-label small">From</label>
                        <input type="number" id="bt-start" class="form-control form-control-sm" value="2010">
                    </div>
                    <div class="col-6">
                        <label class="form-label small">To</label>
                        <input type="number" id="bt-end" class="form-control form-control-sm" value="2024">
                    </div>
                </div>
                <button id="btn-run" class="btn btn-primary w-100">Run Backtest</button>

                <hr>
                <h6 class="small">Saved Strategies</h6>
                <div id="saved-list" class="small" style="max-height:200px;overflow-y:auto"></div>
            </div>
        </div>
    </div>

    <div class="col-md-8">
        <div id="bt-results" style="display:none">
            <div class="row mb-3" id="bt-metrics"></div>
            <canvas id="bt-chart" height="120"></canvas>
            <div class="table-responsive mt-3">
                <table class="table table-sm table-striped" id="bt-cycles">
                    <thead><tr><th>Year</th><th>Entry</th><th>Entry $</th><th>Exit</th><th>Exit $</th><th>Return</th><th>Capital</th></tr></thead>
                    <tbody></tbody>
                </table>
            </div>
        </div>
        <div id="bt-placeholder" class="text-center text-muted py-5">
            Configure and run a backtest to see results
        </div>
    </div>
</div>

<script>
const MONTH_NAMES = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
let btChart = null;

// Populate month selects
MONTH_NAMES.forEach((m, i) => {
    const sel = i === 10 ? ' selected' : '';
    const sel2 = i === 3 ? ' selected' : '';
    $('#bt-entry-month').append(`<option value="${i+1}"${sel}>${m}</option>`);
    $('#bt-exit-month').append(`<option value="${i+1}"${sel2}>${m}</option>`);
});

function runBacktest() {
    $('#btn-run').prop('disabled', true).text('Running...');

    fetchAPI('backtest_run.php', {
        action: 'run',
        ticker: $('#bt-ticker').val(),
        entry_month: $('#bt-entry-month').val(),
        entry_day: $('#bt-entry-day').val(),
        exit_month: $('#bt-exit-month').val(),
        exit_day: $('#bt-exit-day').val(),
        capital: $('#bt-capital').val(),
        year_start: $('#bt-start').val(),
        year_end: $('#bt-end').val(),
    }).done(function(data) {
        renderResults(data);
        loadSaved();
    }).fail(function(xhr) {
        const err = xhr.responseJSON ? xhr.responseJSON.error : 'Request failed';
        alert('Error: ' + err);
    }).always(function() {
        $('#btn-run').prop('disabled', false).text('Run Backtest');
    });
}

function renderResults(data) {
    $('#bt-placeholder').hide();
    $('#bt-results').show();

    const m = data.metrics;
    $('#bt-metrics').html(`
        <div class="col-4 col-md-2"><div class="card text-center p-2"><div class="small text-muted">Total Return</div><div class="fw-bold">${formatPct(m.total_return, 1)}</div></div></div>
        <div class="col-4 col-md-2"><div class="card text-center p-2"><div class="small text-muted">CAGR</div><div class="fw-bold">${formatPct(m.cagr, 1)}</div></div></div>
        <div class="col-4 col-md-2"><div class="card text-center p-2"><div class="small text-muted">Win Rate</div><div class="fw-bold">${m.win_rate.toFixed(0)}%</div></div></div>
        <div class="col-4 col-md-2"><div class="card text-center p-2"><div class="small text-muted">Max DD</div><div class="fw-bold text-danger">${m.max_drawdown.toFixed(1)}%</div></div></div>
        <div class="col-4 col-md-2"><div class="card text-center p-2"><div class="small text-muted">Sharpe</div><div class="fw-bold">${m.sharpe_ratio.toFixed(2)}</div></div></div>
        <div class="col-4 col-md-2"><div class="card text-center p-2"><div class="small text-muted">Cycles</div><div class="fw-bold">${m.winning_cycles}/${m.total_cycles}</div></div></div>
    `);

    // Chart
    if (btChart) btChart.destroy();
    const ctx = document.getElementById('bt-chart').getContext('2d');
    btChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: data.cycles.map(c => c.year),
            datasets: [{
                label: 'Strategy Capital',
                data: data.cycles.map(c => c.capital_end),
                borderColor: '#1a7a3f',
                backgroundColor: 'rgba(26,122,63,0.1)',
                fill: true,
                tension: 0.1,
            }]
        },
        options: {
            responsive: true,
            scales: {
                y: { ticks: { callback: v => '$' + v.toLocaleString() } }
            }
        }
    });

    // Cycles table
    let rows = '';
    data.cycles.forEach(c => {
        const cls = c.return_pct >= 0 ? 'text-success' : 'text-danger';
        rows += `<tr>
            <td>${c.year}</td><td>${c.entry_date}</td><td>$${parseFloat(c.entry_price).toFixed(2)}</td>
            <td>${c.exit_date}</td><td>$${parseFloat(c.exit_price).toFixed(2)}</td>
            <td class="${cls} fw-bold">${formatPct(c.return_pct, 1)}</td>
            <td>$${formatNum(c.capital_end)}</td>
        </tr>`;
    });
    $('#bt-cycles tbody').html(rows);
}

function loadSaved() {
    fetchAPI('backtest_run.php', {action: 'list'}).done(function(data) {
        let html = '';
        (data.strategies || []).slice(0, 10).forEach(s => {
            const cagr = s.cagr ? parseFloat(s.cagr).toFixed(1) + '%' : '—';
            html += `<div class="border-bottom py-1">
                <a href="#" class="load-strategy" data-id="${s.id}">${s.ticker} M${s.entry_month}→M${s.exit_month}</a>
                <span class="text-muted">CAGR: ${cagr}</span>
            </div>`;
        });
        $('#saved-list').html(html || '<em>No saved strategies</em>');
    });
}

$(document).ready(function() {
    loadSaved();
    $('#btn-run').click(runBacktest);
    $(document).on('click', '.load-strategy', function(e) {
        e.preventDefault();
        const id = $(this).data('id');
        fetchAPI('backtest_run.php', {action: 'load', id: id}).done(renderResults);
    });
});
</script>
