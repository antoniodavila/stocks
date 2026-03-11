<?php $ticker = strtoupper(trim($_GET['ticker'] ?? '')); ?>

<div id="company-content">
    <?php if (empty($ticker)): ?>
        <div class="alert alert-warning">No ticker specified. Use ?view=company&ticker=AAPL</div>
    <?php else: ?>
        <div class="text-center py-4"><div class="spinner-border"></div> Loading <?= htmlspecialchars($ticker) ?>...</div>
    <?php endif; ?>
</div>

<?php if (!empty($ticker)): ?>
<script>
const MONTHS_SHORT = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
let ratioChart = null;

fetchAPI('company_data.php', {ticker: '<?= htmlspecialchars($ticker) ?>'}).done(function(d) {
    const c = d.company;
    const score = d.scores[0] || {};
    const sc = scoreClass(score.total_score);
    const trend = score.quality_trend == 1 ? '<span class="text-success">Improving &#9650;</span>' :
                  score.quality_trend == -1 ? '<span class="text-danger">Deteriorating &#9660;</span>' :
                  '<span class="text-muted">Stable &#9654;</span>';

    let html = `
    <div class="d-flex justify-content-between align-items-start mb-3">
        <div>
            <h2>${c.ticker} — ${c.name || ''}</h2>
            <span class="badge bg-secondary">${c.sector || ''}</span>
            <span class="badge bg-light text-dark">${c.industry || ''}</span>
            ${c.market_cap ? '<span class="badge bg-info">MCap: $' + (c.market_cap / 1e9).toFixed(1) + 'B</span>' : ''}
        </div>
        <div class="text-end">
            <div class="${sc}" style="font-size:2rem;font-weight:bold">${score.total_score ? parseFloat(score.total_score).toFixed(1) : '—'}</div>
            <div class="small text-muted">Value Score</div>
        </div>
    </div>`;

    // Score breakdown
    if (score.total_score) {
        const pct = score.sector_percentile ? 'Top ' + (100 - parseFloat(score.sector_percentile)).toFixed(0) + '% in ' + c.sector : '';
        html += `
        <div class="card mb-3"><div class="card-body">
            <h5>Score Breakdown</h5>
            <div class="row text-center">
                <div class="col"><div class="small text-muted">Quality (35%)</div><div class="fw-bold">${parseFloat(score.quality_score || 0).toFixed(1)}</div></div>
                <div class="col"><div class="small text-muted">Valuation (30%)</div><div class="fw-bold">${parseFloat(score.valuation_score || 0).toFixed(1)}</div></div>
                <div class="col"><div class="small text-muted">Solidity (20%)</div><div class="fw-bold">${parseFloat(score.solidity_score || 0).toFixed(1)}</div></div>
                <div class="col"><div class="small text-muted">Growth (15%)</div><div class="fw-bold">${parseFloat(score.growth_score || 0).toFixed(1)}</div></div>
                <div class="col"><div class="small text-muted">Trend</div><div>${trend}</div></div>
            </div>
            <div class="small text-muted mt-2">${pct}</div>
        </div></div>`;
    }

    // Current ratios
    const qr = d.quality_history[0] || {};
    const pr = d.price_history[0] || {};
    html += `
    <div class="card mb-3"><div class="card-body">
        <h5>Current Ratios</h5>
        <div class="row">
            <div class="col-md-3"><strong>Quality</strong><br>
                ROE: ${qr.roe ? (parseFloat(qr.roe)*100).toFixed(1)+'%' : '—'}<br>
                ROIC: ${qr.roic ? (parseFloat(qr.roic)*100).toFixed(1)+'%' : '—'}<br>
                Gross Margin: ${qr.gross_margin ? (parseFloat(qr.gross_margin)*100).toFixed(1)+'%' : '—'}
            </div>
            <div class="col-md-3"><strong>Valuation</strong><br>
                P/E: ${pr.pe_ratio ? parseFloat(pr.pe_ratio).toFixed(1) : '—'}<br>
                P/FCF: ${pr.pfcf_ratio ? parseFloat(pr.pfcf_ratio).toFixed(1) : '—'}<br>
                EV/EBITDA: ${pr.ev_ebitda ? parseFloat(pr.ev_ebitda).toFixed(1) : '—'}
            </div>
            <div class="col-md-3"><strong>Solidity</strong><br>
                D/E: ${qr.debt_equity ? parseFloat(qr.debt_equity).toFixed(2) : '—'}<br>
                Current: ${qr.current_ratio ? parseFloat(qr.current_ratio).toFixed(2) : '—'}
            </div>
            <div class="col-md-3"><strong>Fundamentals</strong><br>
                ${d.fundamentals.length > 0 ? 'Revenue: $' + (parseInt(d.fundamentals[0].revenue)/1e9).toFixed(1) + 'B' : ''}
                ${d.fundamentals.length > 0 && d.fundamentals[0].eps_diluted ? '<br>EPS: $' + parseFloat(d.fundamentals[0].eps_diluted).toFixed(2) : ''}
            </div>
        </div>
    </div></div>`;

    // Ratio history chart
    if (d.quality_history.length > 1) {
        html += `<div class="card mb-3"><div class="card-body">
            <h5>ROE History</h5>
            <canvas id="ratio-chart" height="80"></canvas>
        </div></div>`;
    }

    // Sector seasonality mini-heatmap
    if (d.seasonality.length > 0) {
        html += `<div class="card mb-3"><div class="card-body">
            <h5>Sector Seasonality (${d.etf})</h5>
            <table class="table table-sm table-bordered text-center mb-0"><tr>`;
        MONTHS_SHORT.forEach((m, i) => {
            const s = d.seasonality.find(x => x.month == i + 1);
            const curMonth = new Date().getMonth();
            const highlight = i === curMonth ? 'border: 2px solid #000;' : '';
            if (s) {
                const wr = parseFloat(s.win_rate);
                const bg = wr >= 65 ? 'rgba(40,167,69,0.3)' : wr < 40 ? 'rgba(220,53,69,0.3)' : 'rgba(255,193,7,0.15)';
                html += `<td style="background:${bg};${highlight}" title="WR:${wr.toFixed(0)}% Avg:${parseFloat(s.avg_return).toFixed(1)}%">
                    <div class="small fw-bold">${m}</div>${parseFloat(s.avg_return).toFixed(1)}%</td>`;
            } else {
                html += `<td style="${highlight}"><div class="small">${m}</div>—</td>`;
            }
        });
        html += `</tr></table></div></div>`;
    }

    // AI Narrative
    html += `<div class="card mb-3"><div class="card-body">
        <h5>AI Analysis</h5>
        ${d.narrative ? '<div>' + d.narrative.narrative + '</div><div class="small text-muted mt-1">Generated: ' + d.narrative.generated_at + '</div>' :
        '<p class="text-muted">AI Narrator will be available in M4 (AWS Bedrock integration).</p><button class="btn btn-sm btn-outline-secondary" disabled>Generate AI Analysis</button>'}
    </div></div>`;

    $('#company-content').html(html);

    // Render chart if data exists
    if (d.quality_history.length > 1) {
        const labels = d.quality_history.map(q => q.period).reverse();
        const roeData = d.quality_history.map(q => q.roe ? (parseFloat(q.roe) * 100) : null).reverse();
        const ctx = document.getElementById('ratio-chart').getContext('2d');
        ratioChart = new Chart(ctx, {
            type: 'line',
            data: {
                labels: labels,
                datasets: [{
                    label: 'ROE (%)',
                    data: roeData,
                    borderColor: '#1a7a3f',
                    tension: 0.2,
                }]
            },
            options: { responsive: true, scales: { y: { ticks: { callback: v => v + '%' } } } }
        });
    }
}).fail(function(xhr) {
    const err = xhr.responseJSON ? xhr.responseJSON.error : 'Failed to load';
    $('#company-content').html('<div class="alert alert-danger">' + err + '</div>');
});
</script>
<?php endif; ?>
