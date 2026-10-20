'use strict';
/* Shell: session, routing, top bar, saved user context. */
const App = (() => {
  const {h, api, toast} = UI;
  const state = {role: null, home: null, caseData: null, model: null, legacy: false};
  let pollTimer = null, contextTimer = null, booted = false, renderSeq = 0;
  const main = () => document.getElementById('main');

  async function boot() {
    try {
      await refreshHome();
      const health = await api('/v1/health');
      state.model = health.model; state.legacy = health.legacy_cabinet === true;
      document.getElementById('model-badge').textContent = 'MODEL ' + health.model.mode;
      document.getElementById('model-badge').className = 'badge ' + (health.model.mode === 'LIVE' ? 'blue' : 'warn');
      document.getElementById('boot').hidden = true; document.getElementById('login').hidden = true; document.getElementById('app').hidden = false;
      booted = true;
      if (!location.hash) {
        try { const c = await api('/v1/context'); if (c.context.route && /^#[a-z]/.test(c.context.route)) { location.hash = c.context.route; return; } } catch (_) { /* context is a convenience */ }
        location.hash = '#home';
        return;
      }
      await render();
    } catch (e) {
      if (e.status === 401 || e.code === 'UNAUTHORIZED') return signedOut();
      /* Signed in but the workspace could not load: show the shell with a retry, never a blank page. */
      document.getElementById('boot').hidden = true; document.getElementById('login').hidden = true; document.getElementById('app').hidden = false;
      main().replaceChildren(failure('Could not open the workspace', e, boot));
    }
  }
  function failure(title, e, retry) {
    return h('div', {class: 'card state'}, h('h1', {}, title), h('p', {class: 'notice bad', role: 'alert'}, e.message),
      h('p', {class: 'muted small'}, 'Nothing was changed. If the local server was restarted, try again; amounts and approvals are only ever shown from the server.'),
      h('div', {class: 'row'}, h('button', {class: 'btn primary', type: 'button', onclick: () => retry()}, 'Try again'), h('a', {class: 'btn', href: '#home'}, 'Back to Home')));
  }
  function signedOut() {
    booted = false; state.home = null;
    document.getElementById('boot').hidden = true;
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
    const el = main();
    el.setAttribute('aria-busy', 'true');
    if (!el.firstChild) el.replaceChildren(h('div', {class: 'loading', role: 'status'}, h('span', {class: 'spinner', 'aria-hidden': 'true'}), 'Loading from the server…'));
    const mine = ++renderSeq;
    const m = {replaceChildren: (...nodes) => { if (mine === renderSeq) el.replaceChildren(...nodes); }};
    try {
      if (route === 'home' || !route) await Pages.home(m);
      else if (route === 'money') await Pages.moneyPage(m);
      else if (route === 'case' || route === 'plans') await Pages.casePage(m);
      else if (route === 'review') { await Pages.casePage(m); await Pages.review(a, b); }
      else if (route === 'activity') { refreshHome().catch(() => {}); await Pages.activity(m, a); }
      else if (route === 'documents') { refreshHome().catch(() => {}); await Pages.documents(m); }
      else if (route === 'settings') await Pages.settings(m);
      else m.replaceChildren(h('div', {class: 'card state'}, h('h1', {}, 'Page not found'), h('p', {class: 'muted'}, 'This address is not part of the cabinet.'), h('div', {class: 'row'}, h('a', {class: 'btn primary', href: '#home'}, 'Go to Home'))));
      document.title = (document.querySelector('main h1') || {}).textContent + ' · SME Finance Copilot';
    } catch (e) {
      if (e.status === 401) return;
      m.replaceChildren(failure('Could not load this page', e, render));
    } finally { if (mine === renderSeq) el.setAttribute('aria-busy', 'false'); }
    saveContext(route === 'review' ? '#case' : location.hash);
  }
  function saveContext(route) {
    clearTimeout(contextTimer);
    contextTimer = setTimeout(() => { if (state.role) api('/v1/context', {route}).catch(() => {}); }, 800);
  }
  /* Reviewer demo key: shown only when the server opts in (SME_DEMO_LOGIN_ROLE); never auto-signs in. */
  async function showDemoKey() {
    let demo;
    try { demo = await api('/session/demo'); } catch (_) { return; }
    if (!demo || typeof demo.token !== 'string') return;
    const box = document.getElementById('demo-login');
    const key = h('input', {id: 'demo-token', class: 'mono', type: 'text', readonly: true, value: demo.token, spellcheck: 'false', 'aria-label': 'Demo key'});
    key.addEventListener('focus', () => key.select());
    box.replaceChildren(
      h('h2', {id: 'demo-title'}, 'Demo access for reviewers'),
      h('p', {class: 'small'}, 'Role ' + demo.role + ' · synthetic data, sandbox bank. Payments still need the exact review and step-up.'),
      key,
      h('div', {class: 'row'}, h('button', {class: 'btn', type: 'button', onclick: () => { const f = document.getElementById('token'); f.value = demo.token; f.focus(); }}, 'Use demo key')));
    box.hidden = false;
  }
  /* Personal demo: a fresh synthetic company and OWNER key for this visitor only (SME_DEMO_SELF_SERVICE). */
  async function showPersonalDemo() {
    let info;
    try { info = await api('/session/demo/new'); } catch (_) { return; }
    const box = document.getElementById('personal-demo');
    const err = h('p', {class: 'notice bad', role: 'alert', hidden: true});
    const start = h('button', {class: 'btn primary', type: 'button'}, 'Start a personal demo');
    start.addEventListener('click', async () => {
      err.hidden = true; start.disabled = true; start.textContent = 'Creating your company…';
      try {
        const demo = await api('/session/demo/new', {});
        const key = h('input', {class: 'mono', type: 'text', readonly: true, value: demo.token, spellcheck: 'false', 'aria-label': 'Your demo key'});
        key.addEventListener('focus', () => key.select());
        box.replaceChildren(
          h('h2', {id: 'personal-title'}, 'Your demo company is ready'),
          h('p', {class: 'small'}, 'Save this key to come back: it is shown only once. You will also type it again to approve each payment.'),
          key,
          h('div', {class: 'row'}, h('button', {class: 'btn primary', type: 'button', onclick: () => boot()}, 'Continue')));
        key.focus();
      } catch (e) {
        err.textContent = e.message; err.hidden = false;
        start.disabled = false; start.textContent = 'Start a personal demo';
      }
    });
    box.replaceChildren(
      h('h2', {id: 'personal-title'}, 'New here? Try it with your own company'),
      h('p', {class: 'small'}, 'Creates a fresh synthetic company with its own sandbox bank and your own OWNER key, so you can walk the whole path from the cash gap to reconciliation. Removed after ' + info.idle_hours + ' h without activity.'),
      h('div', {class: 'row'}, start), err);
    box.hidden = false;
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
      const submit = ev.currentTarget.querySelector('button[type=submit]');
      submit.disabled = true; submit.textContent = 'Signing in…';
      try {
        await api('/session', {token: field.value.trim()});
        field.value = '';
        await boot();
      } catch (e) { field.value = ''; err.textContent = e.status === 401 ? 'This token is not valid for this workspace.' : e.message; err.hidden = false; field.focus(); }
      finally { submit.disabled = false; submit.textContent = 'Sign in'; }
    });
    showPersonalDemo();
    showDemoKey();
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
