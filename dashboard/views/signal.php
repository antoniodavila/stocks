<h2>Combined Signal — High Conviction Opportunities</h2>
<div class="view-description mb-3">
    <p>The most powerful view: finds companies where <strong>all three modules agree</strong> — high Value Score + favorable sector seasonality + validated backtest.</p>
    <details>
        <summary>How signals are generated</summary>
        <ul>
            <li><strong>Value Score</strong> &#10003; — Company scores above your minimum threshold (quality + valuation + solidity + growth).</li>
            <li><strong>Sector Seasonality</strong> &#10003; — The company's sector ETF has a historically strong win rate in the target month.</li>
            <li><strong>Backtest Validated</strong> &#10003; — A seasonal strategy for that sector/month has been backtested with positive CAGR and high win rate.</li>
            <li>Only stocks passing <em>all three</em> filters appear. Adjust thresholds to see more or fewer signals.</li>
            <li><strong>Upcoming Favorable Months</strong> below shows which sectors have strong seasonal windows in the next 3 months.</li>
            <li>Rows highlighted in <span class="text-success">green</span> indicate an improving quality trend.</li>
        </ul>
    </details>
</div>

<div class="filter-bar d-flex align-items-center gap-3 flex-wrap">
    <div>
        <label class="form-label mb-0 small">Target Month:</label>
        <select id="sig-month" class="form-select form-select-sm" style="width:130px"></select>
    </div>
    <div>
        <label class="form-label mb-0 small">Min Value Score:</label>
        <input type="number" id="sig-vs" class="form-control form-control-sm" value="70" min="0" max="100" step="5" style="width:80px">
    </div>
    <div>
        <label class="form-label mb-0 small">Min Sector WR:</label>
        <input type="number" id="sig-wr" class="form-control form-control-sm" value="65" min="0" max="100" step="5" style="width:80px">
    </div>
    <div>
        <label class="form-label mb-0 small">Min Backtest WR:</label>
        <input type="number" id="sig-bwr" class="form-control form-control-sm" value="60" min="0" max="100" step="5" style="width:80px">
    </div>
    <button id="btn-signal" class="btn btn-sm btn-primary">Find Signals</button>
    <span id="sig-count" class="badge bg-success ms-2"></span>
</div>

<div class="table-responsive mt-3">
    <table class="table table-sm table-striped" id="signal-table">
        <thead>
            <tr><th>Ticker</th><th>Company</th><th>Sector</th><th>Value Score</th><th>ETF</th>
            <th>Sector WR</th><th>Avg Return</th><th>BT Win Rate</th><th>CAGR</th><th>Trend</th></tr>
        </thead>
        <tbody></tbody>
    </table>
</div>

<div id="sig-empty" class="alert alert-info mt-3" style="display:none">
    No signals found with current thresholds. Try lowering the minimums.
</div>

<h5 class="mt-4">Upcoming Favorable Months</h5>
<div id="upcoming-months" class="row"></div>

<script>
const SIG_MONTHS = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
const currentMonth = new Date().getMonth() + 1;

SIG_MONTHS.forEach((m, i) => {
    const sel = (i + 1) === currentMonth ? ' selected' : '';
    $('#sig-month').append(`<option value="${i+1}"${sel}>${m}</option>`);
});

function loadSignals() {
    fetchAPI('signal_data.php', {
        month: $('#sig-month').val(),
        min_value_score: $('#sig-vs').val(),
        min_winrate: $('#sig-wr').val(),
        min_backtest_wr: $('#sig-bwr').val(),
    }).done(function(data) {
        $('#sig-count').text(data.total + ' signals found');

        if (data.signals.length === 0) {
            $('#signal-table tbody').html('');
            $('#sig-empty').show();
        } else {
            $('#sig-empty').hide();
            let rows = '';
            data.signals.forEach(s => {
                const trendCls = s.quality_trend == 1 ? 'table-success' : '';
                rows += `<tr class="${trendCls}">
                    <td><a href="?view=company&ticker=${s.ticker}">${s.ticker}</a></td>
                    <td>${s.name || ''}</td>
                    <td class="small">${s.sector}</td>
                    <td class="${scoreClass(s.total_score)} fw-bold">${parseFloat(s.total_score).toFixed(1)}</td>
                    <td>${s.sector_etf}</td>
                    <td>${parseFloat(s.sector_win_rate).toFixed(0)}%</td>
                    <td>${formatPct(s.sector_avg_return)}</td>
                    <td>${parseFloat(s.backtest_win_rate).toFixed(0)}%</td>
                    <td>${formatPct(s.backtest_cagr, 1)}</td>
                    <td>${s.quality_trend == 1 ? '&#9650;' : s.quality_trend == -1 ? '&#9660;' : '&#9654;'}</td>
                </tr>`;
            });
            $('#signal-table tbody').html(rows);
        }

        // Upcoming months
        let upcoming = '';
        (data.next_months || []).forEach(nm => {
            upcoming += `<div class="col-md-4"><div class="card mb-2"><div class="card-body p-2">
                <h6>${nm.month_name}</h6>`;
            if (nm.sectors.length === 0) {
                upcoming += '<small class="text-muted">No favorable sectors</small>';
            } else {
                nm.sectors.forEach(s => {
                    upcoming += `<div class="small">${s.ticker}: WR ${parseFloat(s.win_rate).toFixed(0)}%, avg ${formatPct(s.avg_return)}</div>`;
                });
            }
            upcoming += '</div></div></div>';
        });
        $('#upcoming-months').html(upcoming);
    });
}

$(document).ready(function() {
    loadSignals();
    $('#btn-signal').click(loadSignals);
});
</script>
