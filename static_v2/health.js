/* Shows why a panel is empty instead of leaving it blank (added to the page by the server, like auth.js).
   - banner if the Chart.js library did not load (it comes from cdn.jsdelivr.net)
   - banner listing server files that are missing, from GET /api/health
   - window.panelNotice(canvasId, message) puts a message in place of one chart; panelNotice(canvasId) removes it */
(function () {
  const css = `
  .health-banner { margin: 0 0 16px; padding: 12px 40px 12px 16px; border-radius: 10px; font-size: 13px; line-height: 1.5;
    position: relative; background: var(--bg-elevated, #171c27); color: var(--text-secondary, #a3a9b6);
    border: 1px solid rgba(240, 164, 58, 0.45); }
  .health-banner.bad { border-color: rgba(229, 83, 83, 0.6); }
  .health-banner strong { color: var(--text-primary, #eef0f4); }
  .health-banner ul { margin: 6px 0 0 18px; padding: 0; }
  .health-banner button { position: absolute; top: 8px; right: 10px; background: none; border: 0; color: inherit;
    font-size: 18px; cursor: pointer; }
  .panel-notice { display: flex; align-items: center; justify-content: center; text-align: center; height: 100%;
    min-height: 120px; padding: 16px; font-size: 13px; color: var(--text-muted, #727988); }`;
  const style = document.createElement('style');
  style.textContent = css;
  document.head.appendChild(style);

  const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));

  window.panelNotice = function (canvasId, message) {
    const canvas = document.getElementById(canvasId);
    if (!canvas || !canvas.parentNode) return;
    const old = canvas.parentNode.querySelector('.panel-notice[data-for="' + canvasId + '"]');
    if (old) old.remove();
    canvas.style.display = message ? 'none' : '';
    if (!message) return;
    const div = document.createElement('div');
    div.className = 'panel-notice';
    div.dataset.for = canvasId;
    div.textContent = message;
    canvas.parentNode.appendChild(div);
  };

  function banner(id, bad, html) {
    const main = document.getElementById('main-content');
    if (!main) return;
    let el = document.getElementById(id);
    if (!el) {
      el = document.createElement('div');
      el.id = id;
      const bar = main.querySelector('.topbar');
      main.insertBefore(el, bar ? bar.nextSibling : main.firstChild);
    }
    el.className = 'health-banner' + (bad ? ' bad' : '');
    el.innerHTML = html + '<button type="button" aria-label="Dismiss" onclick="this.parentNode.remove()">&times;</button>';
  }

  function checkChartLibrary() {
    if (typeof window.Chart !== 'undefined') return;
    banner('banner-chartjs', true,
      '<strong>The charts cannot be drawn.</strong> The chart library (Chart.js) did not load from cdn.jsdelivr.net. ' +
      'The numbers on this page are fine. Check that this computer can reach that address (firewall, proxy or ad-blocker), then reload.');
    ['chart-cash-trajectory', 'chart-ar-ap-trajectory', 'chart-inflows-outflows', 'chart-revenue-streams',
      'chart-receipts-outlook', 'chart-revenue-forecast', 'ml-canvas'].forEach((id) => window.panelNotice(id, 'Chart library not loaded.'));
  }

  async function checkServer() {
    try {
      const r = await fetch('/api/health');
      if (!r.ok) return;
      const h = await r.json();
      if (h.status === 'ok') return;
      const li = h.checks.filter((c) => !c.ok).map((c) =>
        '<li><strong>' + esc(c.name) + '</strong>' + (c.required ? '' : ' (optional)') + ': ' + esc(c.detail) + (c.fix ? '. ' + esc(c.fix) : '') + '</li>').join('');
      banner('banner-health', h.status === 'broken',
        (h.status === 'broken' ? '<strong>This server is missing files the dashboard needs.</strong>' : '<strong>Some optional features are switched off on this server.</strong>') +
        '<ul>' + li + '</ul>');
    } catch (_) { /* server unreachable: the page's own error toasts already say so */ }
  }

  window.addEventListener('load', () => { checkChartLibrary(); checkServer(); });
})();
