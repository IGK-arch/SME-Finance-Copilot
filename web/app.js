'use strict';
/* Shell: session, routing, top bar, saved user context. */
const App = (() => {
  const {h, api, toast} = UI;
  const state = {role: null, home: null, caseData: null, model: null};
  let pollTimer = null, contextTimer = null, booted = false;
  const main = () => document.getElementById('main');

  async function boot() {
    try {
      await refreshHome();
      const health = await api('/v1/health');
      state.model = health.model;
      document.getElementById('model-badge').textContent = 'MODEL ' + health.model.mode;
      document.getElementById('model-badge').className = 'badge ' + (health.model.mode === 'LIVE' ? 'blue' : 'warn');
      document.getElementById('login').hidden = true; document.getElementById('app').hidden = false;
      booted = true;
      if (!location.hash) {
        try { const c = await api('/v1/context'); if (c.context.route && /^#[a-z]/.test(c.context.route)) { location.hash = c.context.route; return; } } catch (_) { /* context is a convenience */ }
        location.hash = '#home';
        return;
      }
      await render();
    } catch (e) {
      if (e.status === 401 || e.code === 'UNAUTHORIZED') return signedOut();
      main().replaceChildren(h('div', {class: 'notice bad'}, e.message));
    }
  }
  function signedOut() {
    booted = false; state.home = null;
    document.getElementById('app').hidden = true; document.getElementById('login').hidden = false;
    document.getElementById('copilot').hidden = true;
    document.getElementById('token').focus();
  }
  async function signOut() { try { await api('/session/logout', {}); } catch (_) { /* already gone */ } signedOut(); }
  async function refreshHome() {
    const d = await api('/v1/home');
    state.home = d; state.role = d.company.role;
    document.getElementById('company').textContent = d.company.name;
    document.getElementById('asof').textContent = 'Business date ' + UI.dayYear(d.business_as_of);
    document.getElementById('role').textContent = d.company.role;
    const busy = d.alerts.filter(a => a.type === 'UNKNOWN_PAYMENT' || a.type === 'IN_FLIGHT').length;
    const count = document.getElementById('activity-count'); count.hidden = !busy; count.textContent = String(busy);
    return d;
  }
  function poll(condition, ms) { clearTimeout(pollTimer); pollTimer = setTimeout(() => { if (condition()) render(); }, ms); }
  async function render() {
    if (!booted) return;
    clearTimeout(pollTimer);
    const [route, a, b] = (location.hash || '#home').slice(1).split('/');
    const nav = route === 'review' ? 'case' : route;
    document.querySelectorAll('nav.main a').forEach(x => x.setAttribute('aria-current', x.dataset.nav === nav ? 'page' : 'false'));
    const m = main();
    m.setAttribute('aria-busy', 'true');
    try {
      if (route === 'home' || !route) await Pages.home(m);
      else if (route === 'money') await Pages.moneyPage(m);
      else if (route === 'case' || route === 'plans') await Pages.casePage(m);
      else if (route === 'review') { await Pages.casePage(m); await Pages.review(a, b); }
      else if (route === 'activity') { refreshHome().catch(() => {}); await Pages.activity(m, a); }
      else if (route === 'documents') { refreshHome().catch(() => {}); await Pages.documents(m); }
      else if (route === 'settings') await Pages.settings(m);
      else await Pages.home(m);
      document.title = (document.querySelector('main h1') || {}).textContent + ' · SME Finance Copilot';
    } catch (e) {
      if (e.status === 401) return;
      m.replaceChildren(h('div', {class: 'card'}, h('h1', {}, 'Could not load this page'), h('p', {class: 'notice bad', style: {marginTop: '12px'}}, e.message), h('p', {}, h('a', {href: '#home'}, 'Back to Home'))));
    } finally { m.setAttribute('aria-busy', 'false'); }
    saveContext(route === 'review' ? '#case' : location.hash);
  }
  function saveContext(route) {
    clearTimeout(contextTimer);
    contextTimer = setTimeout(() => { if (state.role) api('/v1/context', {route}).catch(() => {}); }, 800);
  }
  let lastRoute = null;
  window.addEventListener('hashchange', () => {
    const route = (location.hash || '').slice(1).split('/')[0];
    const changedPage = route !== lastRoute; lastRoute = route;
    render().then(() => { if (changedPage && route !== 'review') main().focus({preventScroll: false}); });
  });
  document.addEventListener('DOMContentLoaded', () => {
    document.getElementById('login-form').addEventListener('submit', async ev => {
      ev.preventDefault();
      const err = document.getElementById('login-error'); err.hidden = true;
      const field = document.getElementById('token');
      try {
        await api('/session', {token: field.value.trim()});
        field.value = '';
        await boot();
      } catch (e) { field.value = ''; err.textContent = e.status === 401 ? 'This token is not valid for this workspace.' : e.message; err.hidden = false; }
    });
    document.getElementById('open-copilot').addEventListener('click', () => {
      const p = document.getElementById('copilot');
      if (!p.hidden) return Copilot.close();
      const c = state.caseData && state.caseData.case && location.hash.startsWith('#case') ? {case_id: state.caseData.case.case_id} : {};
      Copilot.open(c);
    });
    boot();
  });
  return {state, render, refreshHome, poll, signedOut, signOut, toast};
})();
window.App = App;
