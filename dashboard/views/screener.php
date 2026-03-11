<h2>Value Screener — S&P 500</h2>
<div class="view-description mb-3">
    <p>Ranks all S&P 500 companies by a <strong>Quality-First Value Score</strong> (0-100) combining four weighted dimensions.</p>
    <details>
        <summary>How the score works</summary>
        <ul>
            <li><strong>Quality (35%)</strong> — ROE, ROIC, margins. Measures how well the company generates returns.</li>
            <li><strong>Valuation (30%)</strong> — P/E, P/FCF, EV/EBITDA. Lower = cheaper relative to earnings.</li>
            <li><strong>Solidity (20%)</strong> — Debt/Equity, Current Ratio. Financial health and stability.</li>
            <li><strong>Growth (15%)</strong> — Revenue and EPS growth trends over recent quarters.</li>
            <li><strong>Sector %</strong> — Percentile rank within the company's own sector (90% = top 10%).</li>
            <li><strong>Trend arrows</strong>: <span class="text-success">&#9650;</span> improving quality, <span class="text-danger">&#9660;</span> deteriorating, <span class="text-muted">&#9654;</span> stable.</li>
        </ul>
        <p class="mb-0">Click any column header to sort. Click a ticker to see full company detail.</p>
    </details>
</div>

<div class="filter-bar d-flex align-items-center gap-3 flex-wrap">
    <div>
        <label class="form-label mb-0 small">Sector:</label>
        <select id="filter-sector" class="form-select form-select-sm" style="width:200px">
            <option value="">All Sectors</option>
        </select>
    </div>
    <div>
        <label class="form-label mb-0 small">Min Score:</label>
        <input type="number" id="filter-score" class="form-control form-control-sm" value="0" min="0" max="100" step="5" style="width:80px">
    </div>
    <button id="btn-filter" class="btn btn-sm btn-primary">Filter</button>
    <span id="result-count" class="text-muted small ms-2"></span>
</div>

<div class="table-responsive">
    <table class="table table-sm table-striped table-hover" id="screener-table">
        <thead>
            <tr>
                <th>#</th>
                <th class="sortable" data-sort="ticker">Ticker</th>
                <th>Company</th>
                <th>Sector</th>
                <th class="sortable" data-sort="total_score">Score</th>
                <th class="sortable" data-sort="quality_score">Quality</th>
                <th class="sortable" data-sort="valuation_score">Valuation</th>
                <th class="sortable" data-sort="solidity_score">Solidity</th>
                <th class="sortable" data-sort="growth_score">Growth</th>
                <th class="sortable" data-sort="sector_percentile">Sector %</th>
                <th class="sortable" data-sort="pe_ratio">P/E</th>
                <th class="sortable" data-sort="roe">ROE</th>
                <th class="sortable" data-sort="roic">ROIC</th>
                <th>Trend</th>
            </tr>
        </thead>
        <tbody></tbody>
    </table>
</div>

<div class="d-flex justify-content-between align-items-center mt-2">
    <button id="btn-prev" class="btn btn-sm btn-outline-secondary" disabled>Previous</button>
    <span id="page-info" class="text-muted small"></span>
    <button id="btn-next" class="btn btn-sm btn-outline-secondary">Next</button>
</div>

<script>
let currentPage = 0, currentSort = 'total_score', currentDir = 'DESC', totalResults = 0;
const PAGE_SIZE = 100;

function trendIcon(t) {
    if (t == 1) return '<span class="text-success">&#9650;</span>';
    if (t == -1) return '<span class="text-danger">&#9660;</span>';
    return '<span class="text-muted">&#9654;</span>';
}

function loadScreener() {
    fetchAPI('screener_data.php', {
        sector: $('#filter-sector').val(),
        min_score: $('#filter-score').val(),
        sort_by: currentSort,
        sort_dir: currentDir,
        limit: PAGE_SIZE,
        offset: currentPage * PAGE_SIZE,
    }).done(function(data) {
        totalResults = data.total;
        $('#result-count').text(`Showing ${data.companies.length} of ${data.total} companies`);

        // Populate sectors dropdown (once)
        if ($('#filter-sector option').length <= 1 && data.sectors) {
            data.sectors.forEach(s => {
                $('#filter-sector').append(`<option value="${s}">${s}</option>`);
            });
        }

        let rows = '';
        data.companies.forEach((c, i) => {
            const idx = currentPage * PAGE_SIZE + i + 1;
            const sc = scoreClass(c.total_score);
            rows += `<tr>
                <td>${idx}</td>
                <td><a href="?view=company&ticker=${c.ticker}">${c.ticker}</a></td>
                <td class="text-truncate" style="max-width:180px">${c.name || ''}</td>
                <td class="small">${c.sector || ''}</td>
                <td class="${sc} fw-bold">${c.total_score ? parseFloat(c.total_score).toFixed(1) : '—'}</td>
                <td>${c.quality_score ? parseFloat(c.quality_score).toFixed(1) : '—'}</td>
                <td>${c.valuation_score ? parseFloat(c.valuation_score).toFixed(1) : '—'}</td>
                <td>${c.solidity_score ? parseFloat(c.solidity_score).toFixed(1) : '—'}</td>
                <td>${c.growth_score ? parseFloat(c.growth_score).toFixed(1) : '—'}</td>
                <td>${c.sector_percentile ? parseFloat(c.sector_percentile).toFixed(0) + '%' : '—'}</td>
                <td>${c.pe_ratio ? parseFloat(c.pe_ratio).toFixed(1) : '—'}</td>
                <td>${c.roe ? (parseFloat(c.roe) * 100).toFixed(1) + '%' : '—'}</td>
                <td>${c.roic ? (parseFloat(c.roic) * 100).toFixed(1) + '%' : '—'}</td>
                <td>${trendIcon(c.quality_trend)}</td>
            </tr>`;
        });
        $('#screener-table tbody').html(rows);

        // Pagination
        $('#btn-prev').prop('disabled', currentPage === 0);
        $('#btn-next').prop('disabled', (currentPage + 1) * PAGE_SIZE >= totalResults);
        const totalPages = Math.ceil(totalResults / PAGE_SIZE);
        $('#page-info').text(`Page ${currentPage + 1} of ${totalPages || 1}`);
    });
}

$(document).ready(function() {
    loadScreener();
    $('#btn-filter').click(function() { currentPage = 0; loadScreener(); });
    $('#btn-prev').click(function() { if (currentPage > 0) { currentPage--; loadScreener(); } });
    $('#btn-next').click(function() { currentPage++; loadScreener(); });

    $(document).on('click', 'th.sortable', function() {
        const col = $(this).data('sort');
        if (currentSort === col) {
            currentDir = currentDir === 'DESC' ? 'ASC' : 'DESC';
        } else {
            currentSort = col;
            currentDir = 'DESC';
        }
        currentPage = 0;
        loadScreener();
    });
});
</script>
