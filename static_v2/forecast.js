/* Revenue Forecast page: monthly revenue history + 12-month ML forecast with a likely range.
   Added to the dashboard by the server (forecast.js is injected like ml.js). Data: GET /api/ml/revenue-forecast. */
(function () {
  const $ = (id) => document.getElementById(id);
  const money = (n) => '$' + Math.round(n).toLocaleString('en-US');
  const short = (n) => (Math.abs(n) >= 1e6 ? '$' + (n / 1e6).toFixed(2) + 'M' : '$' + Math.round(n / 1e3) + 'k');
  const COLORS = { history: '#e6e9f0', forecast: '#5b8def', range: '#d9a441' };
  let chart = null;
  let loaded = false;

  const css = `
  .rf-kpis { display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 16px; margin-bottom: 20px; }
  .rf-chart { position: relative; height: 420px; margin-top: 12px; }
  .rf-legend { display: flex; flex-wrap: wrap; gap: 20px; font-size: 12.5px; color: var(--text-secondary); margin-top: 14px; }
  .rf-legend span { display: inline-flex; align-items: center; gap: 8px; }
  .rf-key { width: 22px; height: 0; border-top: 3px solid; }
  .rf-key.dash { border-top-style: dashed; }
  .rf-key.band { height: 12px; border: 0; border-radius: 3px; opacity: .55; }
  .rf-note { font-size: 12.5px; color: var(--text-muted); line-height: 1.5; margin-top: 14px; max-width: 80ch; }
  .rf-tabs { display: flex; gap: 6px; }`;

  function build() {
    const group = $('nav-group-revenue');
    const main = $('main-content');
    if (!group || !main || $('nav-forecast')) return;
    const st = document.createElement('style');
    st.textContent = css;
    document.head.appendChild(st);

    const btn = document.createElement('button');
    btn.className = 'nav-btn';
    btn.id = 'nav-forecast';
    btn.innerHTML = '<svg class="nav-svg" viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M3 16V4"/><path d="M3 16h14"/><path d="M6 12l3-3 3 2 4-5"/></svg> Revenue Forecast';
    btn.onclick = show;
    group.insertBefore(btn, group.firstChild);

    const sec = document.createElement('section');
    sec.className = 'content-section hidden';
    sec.id = 'section-forecast';
    sec.innerHTML = `
      <div class="rf-kpis" id="rf-kpis"></div>
      <div class="chart-card" style="padding:20px 22px">
        <div class="chart-header" style="display:flex;justify-content:space-between;align-items:flex-start;gap:12px">
          <div>
            <h3 style="font-size:15px;margin:0">Monthly revenue: history and next 12 months</h3>
            <div class="rf-note" style="margin-top:4px" id="rf-sub"></div>
          </div>
          <div class="pill-group rf-tabs" id="rf-range">
            <span class="pill" data-m="24">2 years</span>
            <span class="pill active" data-m="all">All</span>
          </div>
        </div>
        <div class="rf-chart"><canvas id="chart-revenue-forecast"></canvas></div>
        <div class="rf-legend">
          <span><i class="rf-key" style="border-color:${COLORS.history}"></i> Actual revenue</span>
          <span><i class="rf-key dash" style="border-color:${COLORS.forecast}"></i> Forecast</span>
          <span><i class="rf-key band" style="background:${COLORS.range}"></i> Likely range (4 in 5 months should land inside)</span>
        </div>
        <div class="rf-note" id="rf-note"></div>
      </div>`;
    main.appendChild(sec);

    sec.querySelectorAll('#rf-range .pill').forEach((p) => {
      p.onclick = () => {
        sec.querySelectorAll('#rf-range .pill').forEach((x) => x.classList.toggle('active', x === p));
        draw(p.dataset.m);
      };
    });

    const orig = window.showSection;
    window.showSection = function () {
      sec.classList.add('hidden');
      btn.classList.remove('active');
      return orig.apply(this, arguments);
    };
  }

  let data = null;

  async function show() {
    document.querySelectorAll('.content-section').forEach((s) => s.classList.add('hidden'));
    document.querySelectorAll('.sidebar-nav .nav-btn').forEach((b) => b.classList.remove('active'));
    $('section-forecast').classList.remove('hidden');
    $('nav-forecast').classList.add('active');
    const t = $('page-title');
    if (t) t.textContent = 'Revenue Forecast';
    if (!loaded) await load();
    else draw(currentRange());
  }

  const currentRange = () => ($('rf-range').querySelector('.active') || {}).dataset?.m || 'all';

  async function load() {
    try {
      const r = await fetch('/api/ml/revenue-forecast');
      const j = await r.json();
      if (!r.ok) throw new Error(j.detail || 'Could not load the forecast');
      data = j;
      loaded = true;
      kpis();
      draw('all');
    } catch (e) {
      $('rf-kpis').innerHTML = `<div class="ml-msg">${String(e.message)}</div>`;
    }
  }

  function kpis() {
    const s = data.summary;
    const card = (label, value, sub) => `<div class="stat-card"><div class="stat-header"><span class="stat-label">${label}</span></div><div class="stat-value">${value}</div><div class="stat-sub">${sub}</div></div>`;
    $('rf-kpis').innerHTML =
      card('Forecast, next 12 months', short(s.next12), `Oct 2026 to Sep 2027`) +
      card('Last 12 months (actual)', short(s.last12), s.growth_pct != null ? `Forecast is ${s.growth_pct > 0 ? '+' : ''}${s.growth_pct}% vs last year` : '') +
      card('Likely range, 12 months', `${short(s.low12)} to ${short(s.high12)}`, 'Wide because growth has been fast');
    $('rf-sub').textContent = data.model;
    const a = data.accuracy;
    $('rf-note').textContent = (a ? `In a test on the last 12 months, a single month's forecast missed by about ${Math.round(a.avg_miss_pct)}% on average, and ${a.inside_range} of ${a.months} months landed inside the range. ` : '') +
      'Treat the line as the most likely path and the shaded band as the realistic range. Forecasts for later months are less certain than near ones.';
  }

  function draw(range) {
    if (!data) return;
    const hist = range === 'all' ? data.history : data.history.slice(-Number(range));
    const labels = hist.map((h) => h.date).concat(data.forecast.map((f) => f.date));
    const nH = hist.length;
    const lastV = hist[nH - 1].revenue;
    const pad = (arr) => new Array(nH - 1).fill(null).concat(arr);
    const histSeries = hist.map((h) => h.revenue).concat(new Array(data.forecast.length).fill(null));
    const fc = pad([lastV].concat(data.forecast.map((f) => f.forecast)));
    const lo = pad([lastV].concat(data.forecast.map((f) => f.low)));
    const hi = pad([lastV].concat(data.forecast.map((f) => f.high)));

    if (chart) chart.destroy();
    const grid = 'rgba(255,255,255,0.06)';
    const tick = '#8c93a3';
    chart = new Chart($('chart-revenue-forecast'), {
      type: 'line',
      data: {
        labels,
        datasets: [
          { label: 'Range low', data: lo, borderColor: 'rgba(217,164,65,0.55)', borderWidth: 1, pointRadius: 0, fill: false, order: 3 },
          { label: 'Likely range', data: hi, borderColor: 'rgba(217,164,65,0.55)', borderWidth: 1, pointRadius: 0, fill: '-1', backgroundColor: 'rgba(217,164,65,0.18)', order: 3 },
          { label: 'Forecast', data: fc, borderColor: COLORS.forecast, borderWidth: 2.5, borderDash: [7, 5], pointRadius: 3, pointBackgroundColor: COLORS.forecast, tension: 0.15, order: 1 },
          { label: 'Actual revenue', data: histSeries, borderColor: COLORS.history, borderWidth: 2, pointRadius: 0, tension: 0.15, order: 2 },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        interaction: { mode: 'index', intersect: false },
        plugins: {
          legend: { display: false },
          tooltip: {
            filter: (i) => i.raw != null,
            callbacks: { label: (c) => ` ${c.dataset.label}: ${money(c.parsed.y)}` },
          },
        },
        scales: {
          x: { grid: { display: false }, ticks: { color: tick, maxTicksLimit: 12, maxRotation: 0, font: { size: 11 } } },
          y: { grid: { color: grid }, ticks: { color: tick, callback: (v) => short(v), font: { size: 11 } }, beginAtZero: true },
        },
      },
    });
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', build);
  else build();
})();
