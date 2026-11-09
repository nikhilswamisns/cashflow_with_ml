/* Login helper for the dashboard (added to the page by the server - index.html is unchanged).
   - shows the logo from the project's logo folder in place of the "CF" box (falls back to "CF")
   - adds the signed-in user and a Logout button at the top right
   - sends the user to the login page if the session has ended (any API call answered 401) */
(function () {
  const realFetch = window.fetch.bind(window);
  let leaving = false;
  window.fetch = async function (input, init) {
    const res = await realFetch(input, init);
    const url = typeof input === 'string' ? input : (input && input.url) || '';
    if (res.status === 401 && url.indexOf('/api/') !== -1 && url.indexOf('/api/auth/') === -1 && !leaving) {
      leaving = true;
      location.href = '/login';
    }
    return res;
  };

  const css = `
  .logo-img { width: 38px; height: 38px; border-radius: 10px; object-fit: contain; display: block;
    box-shadow: 0 4px 12px rgba(37, 99, 235, 0.4); }
  .user-chip { display: inline-flex; align-items: center; gap: 8px; background: var(--bg-elevated);
    border: 1px solid var(--border); border-radius: var(--radius-sm); padding: 3px 3px 3px 10px; }
  .user-name { font-size: 12.5px; color: var(--text-secondary); font-weight: 600; max-width: 140px;
    overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .user-name::before { content: ''; display: inline-block; width: 7px; height: 7px; border-radius: 50%;
    background: var(--emerald); margin-right: 7px; vertical-align: 1px; }
  .btn-logout { padding: 5px 10px; font-size: 12.5px; }`;
  const st = document.createElement('style');
  st.textContent = css;
  document.head.appendChild(st);

  function swapLogo() {
    const box = document.querySelector('.sidebar-logo .logo-icon');
    if (!box) return;
    const img = new Image();
    img.className = 'logo-img';
    img.alt = 'CashFlow';
    img.onload = function () { box.replaceWith(img); };
    img.src = '/brand/logo';
  }

  async function logout() {
    leaving = true;
    try { await realFetch('/api/auth/logout', { method: 'POST', credentials: 'same-origin' }); } catch (e) { /* ignore */ }
    location.href = '/login';
  }

  async function addUserChip() {
    const bar = document.getElementById('more-user') || document.querySelector('.topbar-right');
    if (!bar || document.getElementById('user-chip')) return;
    let user = '';
    try {
      const r = await realFetch('/api/auth/me', { credentials: 'same-origin' });
      if (r.status === 401) { location.href = '/login'; return; }
      user = (await r.json()).user || '';
    } catch (e) { /* offline: still offer logout */ }
    const chip = document.createElement('div');
    chip.className = 'user-chip';
    chip.id = 'user-chip';
    const name = document.createElement('span');
    name.className = 'user-name';
    name.textContent = user || 'Signed in';
    name.title = user ? 'Signed in as ' + user : '';
    const btn = document.createElement('button');
    btn.className = 'btn-secondary btn-logout';
    btn.type = 'button';
    btn.textContent = 'Logout';
    btn.title = 'Sign out of the CashFlow Engine';
    btn.addEventListener('click', logout);
    chip.append(name, btn);
    bar.appendChild(chip);
  }

  function init() { swapLogo(); addUserChip(); }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init); else init();
  window.cfLogout = logout;
})();
