/* ML Forecast page for the dashboard (added to the page by the server - index.html / app.js are unchanged).
   Adds a "ML Forecast" item to the sidebar with:
     - model status, Train model, Backtest, and the ML on/off switch
     - "Compare current run": ending cash with fixed rules vs with ML, with a P10-P90 band
     - the invoices / orders whose expected week moved the most
   All data comes from the /api/ml/... endpoints. */
(function () {
  const API = '/api/ml';
  const $ = (id) => document.getElementById(id);
  const esc = (v) => String(v == null ? '' : v).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const money = (n) => (n < 0 ? '-$' : '$') + Math.abs(Math.round(n)).toLocaleString('en-US');
  let chart = null;

  const css = `
  .ml-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 14px; margin-bottom: 16px; }
  .ml-card { background: var(--bg-surface); border: 1px solid var(--border); border-radius: var(--radius-lg); padding: 16px 18px; }
  .ml-card h4 { margin: 0 0 6px; font-size: 12.5px; color: var(--text-secondary); font-weight: 700; }
  .ml-big { font-size: 22px; font-weight: 800; }
  .ml-sub { font-size: 12px; color: var(--text-muted); margin-top: 4px; line-height: 1.45; }
  .ml-row { display: flex; flex-wrap: wrap; gap: 10px; align-items: center; margin: 10px 0; }
  .ml-pill { display: inline-block; padding: 3px 10px; border-radius: 999px; font-size: 12px; font-weight: 700; }
  .ml-on { background: var(--emerald-subtle); color: var(--emerald); }
  .ml-off { background: var(--amber-subtle); color: var(--amber); }
  .ml-box { background: var(--bg-surface); border: 1px solid var(--border); border-radius: var(--radius-lg); padding: 18px 20px; margin-bottom: 16px; }
  .ml-box h3 { margin: 0 0 4px; font-size: 15px; }
  .ml-table { width: 100%; border-collapse: collapse; font-size: 12.5px; margin-top: 8px; }
  .ml-table th, .ml-table td { padding: 7px 10px; border-bottom: 1px solid var(--border); text-align: left; }
  .ml-table th { color: var(--text-secondary); font-weight: 700; background: var(--bg-elevated); }
  .ml-table td.n, .ml-table th.n { text-align: right; font-variant-numeric: tabular-nums; }
  .ml-good { color: var(--emerald); font-weight: 700; }
  .ml-bad { color: var(--rose); font-weight: 700; }
  .ml-msg { font-size: 13px; padding: 10px 12px; border-radius: var(--radius-sm); background: var(--bg-elevated); margin: 10px 0; }
  .ml-chart { position: relative; height: 340px; margin-top: 10px; }
  .ml-check { font-size: 13px; display: inline-flex; gap: 6px; align-items: center; }
  .ml-adv { margin-top: 8px; }
  .ml-adv > summary { cursor: pointer; font-size: 13px; font-weight: 600; color: var(--text-secondary); padding: 10px 0; }
  .ml-adv[open] > summary { margin-bottom: 12px; }
  .nav-ml-dot { display: inline-block; width: 8px; height: 8px; border-radius: 50%; margin-left: 8px; background: var(--text-muted); }
  .nav-ml-dot.on { background: var(--emerald); }`;
  const st = document.createElement('style');
  st.textContent = css;
  document.head.appendChild(st);

  function build() {
    const nav = document.querySelector('.sidebar-nav');
    const main = document.getElementById('main-content');
    if (!nav || !main || $('nav-ml')) return;

    const btn = document.createElement('button');
    btn.className = 'nav-btn';
    btn.id = 'nav-ml';
    btn.innerHTML = '<svg class="nav-svg" viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M3 15l4-5 3 3 7-8"/><path d="M13 5h4v4"/></svg> Payment Timing (ML) <span class="nav-ml-dot" id="nav-ml-dot"></span>';
    btn.onclick = () => showMl();
    (document.getElementById('nav-group-revenue') || nav).appendChild(btn);

    const sec = document.createElement('section');
    sec.className = 'content-section hidden';
    sec.id = 'section-ml';
    sec.innerHTML = `
      <div class="ml-box">
        <h3>Machine-learning payment timing</h3>
        <div class="ml-sub">Moves invoices and sales orders to the week the cash is expected, based on how each customer has paid before. Amounts never change, only the week.</div>
        <div class="ml-row">
          <span>Use ML in forecasts:</span><span class="ml-pill ml-off" id="ml-state">OFF</span>
          <button class="btn-primary" id="ml-toggle">Switch ON</button>
          <label class="ml-check"><input type="checkbox" id="ml-inv"> Invoices</label>
          <label class="ml-check"><input type="checkbox" id="ml-so"> Sales orders</label>
          <label class="ml-check"><input type="checkbox" id="ml-bill"> Bills <span class="ml-sub">(backtest: rules were better)</span></label>
        </div>
        <div class="ml-sub">Takes effect on the next forecast run.</div>
      </div>

      <details class="ml-adv"><summary>Admin: model training and tests</summary>
      <div class="ml-grid" id="ml-status-cards"></div>
      <div class="ml-row">
        <button class="btn-secondary" id="ml-train">⚙ Train model</button>
        <button class="btn-secondary" id="ml-backtest">📊 Run backtest (about 1 min)</button>
        <button class="btn-primary" id="ml-compare">⚖ Compare current run: rules vs ML</button>
      </div>
      <div id="ml-msg"></div>

      <div class="ml-box" id="ml-backtest-box" style="display:none"></div>
      <div class="ml-box" id="ml-compare-box" style="display:none"></div>
      </details>`;
    main.appendChild(sec);

    $('ml-train').onclick = train;
    $('ml-backtest').onclick = backtest;
    $('ml-compare').onclick = compare;
    $('ml-toggle').onclick = toggle;
    ['ml-inv', 'ml-so', 'ml-bill'].forEach((id) => { $(id).onchange = saveTypes; });

    // keep the other sidebar items working: hide our page when another page is opened
    const orig = window.showSection;
    window.showSection = function (name) {
      sec.classList.add('hidden');
      btn.classList.remove('active');
      return orig.apply(this, arguments);
    };
    refreshStatus();
  }

  function showMl() {
    document.querySelectorAll('.content-section').forEach((s) => s.classList.add('hidden'));
    document.querySelectorAll('.sidebar-nav .nav-btn').forEach((b) => b.classList.remove('active'));
    $('section-ml').classList.remove('hidden');
    $('nav-ml').classList.add('active');
    const t = $('page-title');
    if (t) t.textContent = 'Payment Timing (ML)';
    refreshStatus();
  }

  function msg(text, kind) {
    $('ml-msg').innerHTML = text ? `<div class="ml-msg ${kind === 'bad' ? 'ml-bad' : ''}">${esc(text)}</div>` : '';
  }
  function busy(id, on, label) {
    const b = $(id);
    if (!b) return;
    if (on) { b.dataset.l = b.textContent; b.textContent = label || 'Working...'; b.disabled = true; }
    else { b.textContent = b.dataset.l || b.textContent; b.disabled = false; }
  }
  async function call(url, opt) {
    const r = await fetch(url, opt);
    let j = null;
    try { j = await r.json(); } catch (e) { /* not json */ }
    if (!r.ok) throw new Error((j && (j.detail || j.message)) || `Request failed (${r.status})`);
    return j;
  }

  let state = null;
  async function refreshStatus() {
    try {
      state = await call(`${API}/status`);
    } catch (e) { msg(e.message, 'bad'); return; }
    const on = !!state.enabled_in_rules;
    $('ml-state').textContent = on ? 'ON' : 'OFF';
    $('ml-state').className = 'ml-pill ' + (on ? 'ml-on' : 'ml-off');
    $('ml-toggle').textContent = on ? 'Switch OFF' : 'Switch ON';
    $('nav-ml-dot').className = 'nav-ml-dot' + (on ? ' on' : '');
    $('ml-inv').checked = !!(state.use_for || {}).invoices;
    $('ml-so').checked = !!(state.use_for || {}).sales_orders;
    $('ml-bill').checked = !!(state.use_for || {}).bills;
    const cards = [];
    if (!state.trained) {
      cards.push(`<div class="ml-card"><h4>Model</h4><div class="ml-big ml-bad">Not trained</div>
        <div class="ml-sub">${state.history_file_found ? 'History file found: ' + esc(state.history_file_found) + '. Click Train model.' :
        'Put Zoho_history_*.xlsx into the ml_data folder, then click Train model.'}</div></div>`);
    } else {
      const names = { inv: 'Customer invoices', so: 'Sales orders', bill: 'Vendor bills' };
      cards.push(`<div class="ml-card"><h4>Model</h4><div class="ml-big ml-good">Trained</div>
        <div class="ml-sub">${esc((state.trained_at || '').replace('T', ' ').slice(0, 16))} UTC<br>from ${esc(state.history_file || '')}</div></div>`);
      Object.keys(state.models || {}).forEach((k) => {
        const m = state.models[k];
        cards.push(`<div class="ml-card"><h4>${esc(names[k] || k)}</h4>` + (m.trained
          ? `<div class="ml-big">${Number(m.rows).toLocaleString()}</div><div class="ml-sub">past payments learned from, ${m.parties} customers/vendors, history to ${esc(m.trained_through)}</div>`
          : `<div class="ml-big ml-bad">not trained</div><div class="ml-sub">${esc(m.reason || '')}</div>`) + '</div>');
      });
    }
    $('ml-status-cards').innerHTML = cards.join('');
  }

  async function toggle() {
    const want = !(state && state.enabled_in_rules);
    try {
      await call(`${API}/settings`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ enabled: want }) });
      msg(want ? 'ML timing is ON. Create a new run (Sync Zoho) to see it in the dashboard and the Excel export.' : 'ML timing is OFF. New runs use the fixed rules again.');
    } catch (e) { msg(e.message, 'bad'); }
    refreshStatus();
  }
  async function saveTypes() {
    try {
      await call(`${API}/settings`, { method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ invoices: $('ml-inv').checked, sales_orders: $('ml-so').checked, bills: $('ml-bill').checked }) });
      msg('Saved. Applies from the next forecast run.');
    } catch (e) { msg(e.message, 'bad'); }
  }

  async function train() {
    busy('ml-train', true, 'Training...');
    msg('Training on the Zoho history (about 15 seconds)...');
    try { await call(`${API}/train`, { method: 'POST' }); msg('Model trained.'); }
    catch (e) { msg(e.message, 'bad'); }
    busy('ml-train', false);
    refreshStatus();
  }

  async function backtest() {
    busy('ml-backtest', true, 'Testing...');
    msg('Walk-forward test running (about 1 minute). It trains only on data before each cut-off and checks what really happened.');
    try {
      const r = await call(`${API}/backtest`, { method: 'POST' });
      const names = { inv: 'Customer invoices', so: 'Sales orders', bill: 'Vendor bills' };
      let rows = '';
      Object.keys(r).forEach((k) => {
        const a = r[k].average.rule, b = r[k].average.ml;
        const better = (x, y, lowerIsBetter) => (lowerIsBetter ? y < x : y > x) ? 'ml-good' : 'ml-bad';
        rows += `<tr><td>${esc(names[k] || k)}</td>
          <td class="n">${a.median_abs_err_days}</td><td class="n ${better(a.median_abs_err_days, b.median_abs_err_days, true)}">${b.median_abs_err_days}</td>
          <td class="n">${a.within_1wk_pct}%</td><td class="n ${better(a.within_1wk_pct, b.within_1wk_pct, false)}">${b.within_1wk_pct}%</td></tr>`;
      });
      const box = $('ml-backtest-box');
      box.style.display = '';
      box.innerHTML = `<h3>Backtest: would ML have beaten the fixed rules?</h3>
        <div class="ml-sub">Average over several past cut-off dates. Green = ML better, red = ML worse. "Within 1 week" = share of documents placed within one week of the day they were really paid.</div>
        <table class="ml-table"><tr><th>Document</th><th class="n">Rules: typical error (days)</th><th class="n">ML: typical error (days)</th>
        <th class="n">Rules: within 1 week</th><th class="n">ML: within 1 week</th></tr>${rows}</table>`;
      msg('');
    } catch (e) { msg(e.message, 'bad'); }
    busy('ml-backtest', false);
  }

  async function compare() {
    const runId = typeof currentRunId !== 'undefined' ? currentRunId : null;
    if (!runId) { msg('No run selected. Create or pick a run first (Sync Zoho).', 'bad'); return; }
    if (!state || !state.trained) { msg('Train the model first.', 'bad'); return; }
    busy('ml-compare', true, 'Comparing...');
    msg('Forecasting this run twice (rules and ML) and simulating payment timing. A few seconds...');
    try {
      const d = await call(`${API}/runs/${runId}/compare`);
      msg('');
      renderCompare(d);
    } catch (e) { msg(e.message, 'bad'); }
    busy('ml-compare', false);
  }

  function renderCompare(d) {
    const n = d.weeks.length;
    const R = d.ending_cash_rules, M = d.ending_cash_ml, lo = d.bands.p10, hi = d.bands.p90;
    const low = (arr) => { let i = 0; arr.forEach((v, k) => { if (v < arr[i]) i = k; }); return { i, v: arr[i] }; };
    const lr = low(R), lm = low(M);
    const at = (arr, w) => arr[Math.min(w, n) - 1];
    const card = (t, a, b, sub) => `<div class="ml-card"><h4>${t}</h4>
      <div class="ml-sub">Rules</div><div class="ml-big">${money(a)}</div>
      <div class="ml-sub">With ML</div><div class="ml-big ${b >= a ? 'ml-good' : 'ml-bad'}">${money(b)}</div><div class="ml-sub">${sub || ''}</div></div>`;
    const cards = [
      card('Ending cash, week 4', at(R, 4), at(M, 4)),
      card('Ending cash, week 13', at(R, 13), at(M, 13)),
      card('Lowest cash point', lr.v, lm.v, `rules: week ${lr.i + 1} · ML: week ${lm.i + 1}`),
      `<div class="ml-card"><h4>Lines re-timed by ML</h4><div class="ml-big">${d.ml_lines}</div>
        <div class="ml-sub">invoices / orders whose expected week moved. Amounts are unchanged.</div></div>`,
    ].join('');
    const lines = (d.lines_retimed || []).slice(0, 25).map((l) => `<tr><td>${esc(l.source)}</td><td>${esc(l.ref)}</td><td>${esc(l.party)}</td>
      <td class="n">${money(l.amount)}</td><td>${esc(l.week)}</td><td>${esc(l.expected)}</td>
      <td class="n ${l.shift_days < 0 ? 'ml-good' : 'ml-bad'}">${l.shift_days > 0 ? '+' : ''}${l.shift_days} d</td>
      <td>${esc(l.p10)} to ${esc(l.p90)}</td></tr>`).join('');
    const box = $('ml-compare-box');
    box.style.display = '';
    box.innerHTML = `<h3>Rules vs ML for the selected run</h3>
      <div class="ml-sub">${esc(d.note)} The shaded band is the P10 to P90 range of ending cash if payments come earlier or later than expected.
      Negative days = ML expects the cash earlier than the rule.</div>
      <div class="ml-grid" style="margin-top:12px">${cards}</div>
      <div class="ml-chart"><canvas id="ml-canvas"></canvas></div>
      <h3 style="margin-top:18px">Largest changes (top 25 by amount × days moved)</h3>
      <div style="overflow-x:auto"><table class="ml-table"><tr><th>Type</th><th>Ref</th><th>Customer / vendor</th><th class="n">Amount</th>
      <th>Week (ML)</th><th>Expected date</th><th class="n">Shift vs rule</th><th>Likely range</th></tr>${lines}</table></div>`;
    if (typeof Chart === 'undefined') { $('ml-canvas').parentNode.innerHTML = '<div class="ml-msg">Chart library not loaded (needs internet access to cdn.jsdelivr.net). Figures above are still valid.</div>'; return; }
    if (chart) chart.destroy();
    const labels = d.weeks.map((w, i) => `W${i + 1} ${w.slice(5)}`);
    const line = (label, data, color, extra) => Object.assign({ label, data, borderColor: color, backgroundColor: color, pointRadius: 0, borderWidth: 2, tension: 0.15 }, extra || {});
    chart = new Chart($('ml-canvas'), {
      type: 'line',
      data: { labels, datasets: [
        line('P10 (late payments)', lo, 'rgba(91,141,239,0.0)', { fill: '+1', backgroundColor: 'rgba(91,141,239,0.16)', borderWidth: 0 }),
        line('P90 (early payments)', hi, 'rgba(91,141,239,0.0)', { borderWidth: 0 }),
        line('Fixed rules', R, '#8b93a5', { borderDash: [6, 4] }),
        line('With ML', M, '#5b8def'),
      ] },
      options: { responsive: true, maintainAspectRatio: false, interaction: { mode: 'index', intersect: false },
        plugins: { legend: { labels: { color: '#8c93a3', filter: (i) => !i.text.startsWith('P90') } },
          tooltip: { callbacks: { label: (c) => `${c.dataset.label}: ${money(c.parsed.y)}` } } },
        scales: { x: { ticks: { color: '#8c93a3', maxTicksLimit: 14 }, grid: { color: 'rgba(255,255,255,0.05)' } },
          y: { ticks: { color: '#8c93a3', callback: (v) => money(v) }, grid: { color: 'rgba(255,255,255,0.05)' } } } },
    });
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', build);
  else build();
})();
