'use strict';
/* Context-aware Copilot panel over the real LangGraph workflow.
   Verified tool results are shown as cards as soon as they are recorded; the model's
   narrative is shown separately and labelled as not financial evidence. */
const Copilot = (() => {
  const {h, api, toast, time, statusBadge} = UI;
  let context = {}, runId = null, timer = null, last = null, startedAt = null;
  const panel = () => document.getElementById('copilot');
  const SUGGEST = {
    home: ['How much confirmed cash do we have?', 'Why is there a cash gap?', 'What is due this week?'],
    case: ['Why is there a gap, and what are my options?', 'Compare the financing cost with no new debt', 'What happens if the customer pays 25 days late?'],
    money: ['What if the customer pays 10 days late?', 'Which payments are protected?'],
    documents: ['Which imported rows need review and why?'],
    activity: ['What is the status of the last operation?'],
  };
  function routeName() { return (location.hash || '#home').slice(1).split('/')[0] || 'home'; }
  function open(ctx, prefill) {
    context = Object.assign({route: location.hash || '#home'}, ctx || {});
    panel().hidden = false; document.getElementById('open-copilot').setAttribute('aria-expanded', 'true');
    render(prefill);
    const ta = panel().querySelector('textarea'); if (ta) ta.focus();
  }
  function close() { panel().hidden = true; document.getElementById('open-copilot').setAttribute('aria-expanded', 'false'); clearTimeout(timer); document.getElementById('open-copilot').focus(); }
  function contextChips() {
    const names = {home: 'Home', money: 'Money', case: 'Plans', plans: 'Plans', review: 'Review of an action', documents: 'Documents', activity: 'Activity', settings: 'Settings'};
    const screen = (context.route || '#home').slice(1).split('/');
    const chips = [h('span', {class: 'chip'}, 'Screen: ' + (names[screen[0]] || 'Home') + (screen[0] === 'activity' && screen[1] ? ' · one operation' : ''))];
    if (context.case_id) chips.push(h('span', {class: 'chip'}, 'Financial task'));
    if (context.plan_id) chips.push(h('span', {class: 'chip'}, 'Plan …' + context.plan_id.slice(-6)));
    if (context.obligation_id) chips.push(h('span', {class: 'chip'}, 'Obligation ' + context.obligation_id));
    return h('div', {class: 'row'}, h('span', {class: 'small muted'}, 'Context:'), chips);
  }
  function render(prefill) {
    const p = panel();
    const mode = (App.state.model || {}).mode || '—';
    const task = h('textarea', {id: 'cp-task', rows: 3, 'aria-label': 'Your question or task', placeholder: 'Ask about cash, the gap, options or an operation'}, prefill || '');
    const form = h('form', {onsubmit: ev => { ev.preventDefault(); start(task.value); }},
      h('div', {class: 'suggest'}, (SUGGEST[routeName()] || SUGGEST.home).map(s => h('button', {type: 'button', onclick: () => { task.value = s; }}, s))),
      task, h('div', {class: 'row between'}, h('span', {class: 'small muted'}, mode === 'MOCK' ? 'MOCK: deterministic fixture, not language understanding' : mode === 'LIVE' ? 'Local model · results come from tools' : 'Model disabled'),
        h('button', {class: 'btn primary small', type: 'submit', disabled: !['OWNER', 'ACCOUNTANT'].includes(App.state.role)}, 'Ask')));
    p.replaceChildren(
      h('header', {}, h('div', {}, h('h2', {}, 'Copilot'), h('span', {class: 'badge ' + (mode === 'LIVE' ? 'blue' : 'warn')}, 'MODEL ' + mode)), h('button', {class: 'btn link', type: 'button', 'aria-label': 'Close Copilot', onclick: close}, '✕')),
      h('div', {class: 'scroll', id: 'cp-scroll', 'aria-live': 'polite'}, contextChips(), last ? view(last) : intro()),
      form);
  }
  function intro() {
    return h('div', {class: 'stack'}, h('p', {class: 'small muted'}, 'Copilot runs the real workflow graph with the allowed tools. Numbers in cards come from those tools; the written explanation is a model narrative. It can propose an action, but only you approve the exact command.'),
      h('button', {class: 'btn small', type: 'button', onclick: history}, 'Open a previous conversation'));
  }
  async function history() {
    const r = await api('/v1/workflows');
    const scroll = document.getElementById('cp-scroll');
    scroll.append(h('div', {class: 'stack'}, r.workflows.slice(0, 10).map(w => h('button', {class: 'btn small', type: 'button', onclick: () => { runId = w.run_id; poll(); }}, (w.task.split('User task: ').pop() || w.task).slice(0, 60) + ' · ' + w.status))));
  }
  async function start(text) {
    if (!text.trim()) return;
    try {
      const r = await api('/v1/workflows', {task: text.trim(), context: clean(context), background: true});
      runId = r.workflow_id; startedAt = Date.now(); last = {statuses: {workflow: 'STARTING', computation: 'RUNNING', narrative: 'WRITING'}, task: text, cards: [], stages: [], pending: [], errors: []};
      render(); poll();
    } catch (e) { toast(e.message, 'bad'); }
  }
  function clean(c) { const o = {}; for (const k of ['case_id', 'plan_id', 'obligation_id', 'action_id', 'route']) if (c[k]) o[k] = String(c[k]); return o; }
  async function resume(value) {
    try { await api('/v1/workflows/' + runId + '/resume', Object.assign({background: true}, value)); startedAt = Date.now(); last.statuses.workflow = 'RESUMING'; render(); poll(); } catch (e) { toast(e.message, 'bad'); }
  }
  async function poll() {
    clearTimeout(timer);
    if (!runId) return;
    try { last = await api('/v1/copilot/' + runId); } catch (e) { if (e.code !== 'NOT_FOUND') { toast(e.message, 'bad'); return; } }
    if (!panel().hidden) render();
    const wf = last && last.statuses.workflow;
    if (!last || ['RUNNING', 'STARTING', 'RESUMING'].includes(wf)) timer = setTimeout(poll, 1000);
    else if (wf !== 'FAILED') App.refreshHome().catch(() => {});
  }
  function view(r) {
    const s = r.statuses;
    const running = ['RUNNING', 'STARTING', 'RESUMING'].includes(s.workflow);
    const elapsed = startedAt ? Math.round((Date.now() - startedAt) / 1000) : null;
    const nodes = [h('div', {class: 'result'}, h('p', {class: 'small muted'}, 'You asked'), h('p', {}, (r.task || '').split('User task: ').pop()))];
    nodes.push(h('div', {class: 'row'}, statusBadge(s.workflow === 'FAILED' ? 'FAILED_WF' : s.workflow), h('span', {class: 'badge'}, 'Results: ' + s.computation.toLowerCase().replace('_', ' ')), h('span', {class: 'badge'}, 'Explanation: ' + s.narrative.toLowerCase().replace('_', ' '))));
    if (running) nodes.push(h('p', {class: 'stages'}, 'Real stages: ' + (r.stages || []).map(x => x.node).slice(-6).join(' → ') + (elapsed !== null ? ` · ${elapsed}s` : '') + '. You can leave this page; the run continues on the server.'));
    for (const c of r.cards || []) nodes.push(card(c));
    if (r.partial_note) nodes.push(h('div', {class: 'notice warn'}, r.partial_note));
    if (r.answer) nodes.push(h('div', {}, h('p', {class: 'small muted'}, 'Model explanation · not financial evidence'), h('div', {class: 'narrative'}, r.answer.text)));
    for (const e of r.errors || []) nodes.push(h('div', {class: 'notice bad'}, (e.safe_message || 'Stopped') + ' (' + (e.code || 'ERROR') + '). No success is asserted.'));
    for (const p of r.pending || []) nodes.push(pending(p));
    if (r.usage && r.usage.calls) nodes.push(h('p', {class: 'stages'}, `${r.usage.calls} model calls · ${r.usage.tokens || 0} reported tokens · ${Number(r.usage.elapsed_seconds || 0).toFixed(1)} s model time`));
    return h('div', {class: 'stack'}, nodes);
  }
  function rows(list) { return h('dl', {class: 'kv'}, list.flatMap(([k, v]) => [h('dt', {}, k), h('dd', {}, v)])); }
  const app = (box, ...nodes) => box.append(...nodes.filter(x => x !== null && x !== undefined && x !== false));
  function card(c) {
    const box = h('div', {class: 'result'}, h('h4', {}, c.title || c.type));
    if (c.type === 'cash') app(box, h('div', {class: 'big num'}, c.value.display), h('p', {class: 'small muted'}, c.note + ' As of ' + time(c.as_of) + '.'), evidenceLinks(c.evidence));
    else if (c.type === 'forecast') app(box, UI.table(['Scenario', 'Lowest cash', 'First gap', 'Need'], c.rows.map(x => [x.scenario, x.minimum.display, x.first_gap_at ? UI.day(x.first_gap_at) : 'none', x.need.display]), {right: [1, 3]}), c.note ? h('p', {class: 'small muted'}, c.note) : null);
    else if (c.type === 'metrics' || c.type === 'quote') app(box, rows(c.rows.map(x => [x.name, x.value.display])), c.note ? h('p', {class: 'small muted'}, c.note) : null, c.repay_at ? h('p', {class: 'small muted'}, 'Repay ' + UI.day(c.repay_at)) : null);
    else if (c.type === 'eligibility') app(box, rows(c.rows.map(x => [x.product_id, x.status + (x.missing.length ? ' · missing ' + x.missing.join(', ') : '')])), h('p', {class: 'small muted'}, 'DEMO conditions; not lender approval.'));
    else if (c.type === 'plan') app(box, rows([['Solver', c.solver_status], ['Total cost', c.total_cost ? c.total_cost.display : '—'], ['Actions', String(c.actions)]]), c.reason ? h('p', {class: 'small muted'}, c.reason) : null, c.plan_id ? h('a', {href: '#case', class: 'small'}, 'Compare in Plans →') : null);
    else if (c.type === 'documents') app(box, h('ul', {class: 'reasons'}, c.rows.map(x => h('li', {}, x.title + ' · line ' + x.line, ' ', h('button', {class: 'btn link small', type: 'button', onclick: () => Pages.evidence(x.source_id)}, 'Source')))));
    else if (c.type === 'evidence') app(box, h('button', {class: 'btn link small', type: 'button', onclick: () => Pages.evidence(c.source_id)}, 'Open source'));
    else if (c.type === 'proposal') app(box, h('p', {class: 'small'}, 'A proposal, not an approval.'), h('a', {class: 'btn small', href: `#review/${c.plan_id}/${c.action_id}`}, 'Review exact action'));
    else if (c.type === 'operation') app(box, statusBadge(c.status), ' ', h('a', {href: '#activity/' + c.action_id, class: 'small'}, 'Open timeline'));
    else if (c.type === 'conditional') app(box, h('p', {class: 'small'}, c.status + ' · ' + c.note));
    else if (c.type === 'error') { box.classList.add('notice', 'bad'); app(box, h('p', {class: 'small'}, (c.tool || '') + ': ' + (c.text || c.code))); }
    else if (c.type === 'read') app(box, h('p', {class: 'small muted'}, 'Read ' + (c.detail || 'records')));
    return box;
  }
  function evidenceLinks(ids) { return ids && ids.length ? h('div', {class: 'row'}, h('span', {class: 'small muted'}, 'Sources:'), ids.slice(0, 4).map(id => h('button', {class: 'btn link small', type: 'button', onclick: () => Pages.evidence(id)}, '…' + id.slice(-6)))) : null; }
  function pending(p) {
    if (p.kind === 'CLARIFICATION') {
      const a = h('input', {'aria-label': 'Your answer'});
      return h('div', {class: 'result'}, h('h4', {}, 'Copilot needs your answer'), h('p', {}, p.question), a, h('button', {class: 'btn small primary', type: 'button', style: {marginTop: '8px'}, onclick: () => a.value.trim() && resume({text: a.value.trim()})}, 'Answer and continue'));
    }
    if (p.kind === 'EXACT_APPROVAL') {
      const c = p.command;
      return h('div', {class: 'result'}, h('h4', {}, 'Waiting for your exact approval'), h('p', {}, c.kind + ' · ' + UI.minorText(c.amount_minor) + ' · due ' + UI.day(c.at)),
        h('p', {class: 'small muted'}, 'Copilot cannot approve. Review and approve it yourself, then let the workflow observe the result.'),
        h('div', {class: 'row'}, h('a', {class: 'btn small primary', href: `#review/${c.plan_id}/${c.action_id}`}, 'Review exact action'), h('button', {class: 'btn small', type: 'button', onclick: () => resume({payload_hash: p.payload_hash})}, 'I approved it — continue'), h('button', {class: 'btn small', type: 'button', onclick: () => resume({refresh_command: true})}, 'Refresh command')));
    }
    if (p.kind === 'WAITING_EVENT') return h('div', {class: 'result'}, h('h4', {}, 'Waiting for a date or settlement'), h('p', {class: 'small'}, 'Next action is due ' + UI.day(p.at) + ' (' + p.reason + ').'), h('div', {class: 'row'}, h('button', {class: 'btn small', type: 'button', onclick: () => resume({})}, 'Check again'), h('button', {class: 'btn small', type: 'button', onclick: () => resume({replan: true})}, 'Replan from current facts')));
    if (p.kind === 'OBSERVATION') return h('div', {class: 'result'}, h('h4', {}, 'Operation sent'), h('p', {class: 'small'}, 'Status ' + p.status + '. ' + p.question), h('button', {class: 'btn small', type: 'button', onclick: () => resume({})}, 'Observe again'));
    return null;
  }
  document.addEventListener('keydown', ev => { if (ev.key === 'Escape' && !panel().hidden && !document.getElementById('dialog').open) close(); });
  return {open, close};
})();
