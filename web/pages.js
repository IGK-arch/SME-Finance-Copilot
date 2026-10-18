'use strict';
/* Pages of the owner cabinet. Every number comes from the backend read models. */
const Pages = (() => {
  const {h, day, time, api, toast, statusBadge, metric, table, chart} = UI;
  const COLORS = {f0: '#141413', delay_5: '#827DBD', delay_25: '#9E2F2A', plan: '#2F6B5A', what_if: '#6A5FA8'};
  const can = roles => roles.includes(App.state.role);
  const head = (title, sub, ...actions) => h('div', {class: 'pagehead'}, h('div', {}, h('h1', {}, title), sub ? h('p', {}, sub) : null), h('div', {class: 'row'}, actions));
  const sourceButton = id => id ? h('button', {class: 'btn link small', type: 'button', onclick: () => evidence(id).catch(e => toast(e.message, 'bad'))}, 'Source') : '';
  const money = m => h('span', {class: 'num'}, m.display);
  const put = (main, ...nodes) => main.replaceChildren(...nodes.flat().filter(Boolean));
  function guard(fn) {
    return async ev => {
      const b = ev && ev.currentTarget;
      if (b && b.tagName === 'BUTTON') b.disabled = true;
      try { await fn(ev); } catch (e) { toast(e.message, 'bad'); } finally { if (b && b.tagName === 'BUTTON' && b.isConnected) b.disabled = false; }
    };
  }

  async function evidence(sourceId) {
    const d = await api('/v1/evidence/' + encodeURIComponent(sourceId));
    Dialog.open(h('div', {class: 'head'}, h('div', {}, h('h2', {id: 'dialog-title'}, 'Source record'), h('p', {class: 'muted small'}, 'Observed ' + time(d.observed_at) + ' · ' + d.trust)), Dialog.close()),
      h('div', {class: 'body stack'}, h('p', {class: 'small muted'}, 'Shown as data. Text inside a source is never treated as an instruction.'), h('pre', {}, d.text), h('p', {class: 'small muted'}, 'SHA-256 ' + d.hash)),
      h('div', {class: 'foot'}, h('button', {class: 'btn', type: 'button', onclick: () => Dialog.dismiss()}, 'Close')));
  }

  /* ---------------------------------------------------------------- Home */
  async function home(main) {
    const d = await App.refreshHome();
    const m = d.metrics;
    const series = d.chart.series.filter(s => s.scenario_id === 'f0' || s.scenario_id === 'delay_25').map(s => ({
      name: s.scenario_id === 'f0' ? 'Contract dates (f0)' : 'Customer 25 days late (DEMO stress)', color: COLORS[s.scenario_id], dash: s.scenario_id === 'f0' ? null : '5 4', points: s.points}));
    const alerts = d.alerts.slice(0, 5);
    put(main, 
      head('Home', 'Your cash position, decisions and next steps. Business date ' + UI.dayYear(d.business_as_of) + ' (sandbox clock).'),
      issueCard(d),
      h('div', {class: 'grid g4', style: {marginTop: '16px'}},
        metric('Confirmed cash', m.confirmed_cash, 'Settled observations only'),
        metric('Lowest projected cash', m.expected_minimum, 'Contract dates · expected, not settled', m.expected_minimum.minor < m.reserve.minor),
        metric('Hard reserve', m.reserve, 'Plans must keep at least this'),
        metric('Reserved for operations', m.reserved, 'Held until reconciliation')),
      h('div', {class: 'split'},
        h('section', {class: 'card', 'aria-labelledby': 'h-chart'}, h('div', {class: 'row between'}, h('h2', {id: 'h-chart'}, 'Cash forecast'), h('a', {href: '#money', class: 'small'}, 'Explore scenarios →')),
          h('p', {class: 'muted small'}, 'Cashflow · expected, not settled. Scenarios are uncalibrated DEMO assumptions, not probabilities.'),
          chart(series, d.chart.reserve, {label: 'Projected cash on contract dates and a late-payment stress', share: 0.61})),
        h('section', {class: 'card', 'aria-labelledby': 'h-tasks'}, h('h2', {id: 'h-tasks'}, 'Needs your attention'),
          alerts.length ? h('div', {class: 'tasks', style: {marginTop: '12px'}}, alerts.map(a => h('div', {class: 'task ' + a.severity}, h('span', {class: 'sev', 'aria-hidden': 'true'}),
            h('div', {class: 'body'}, h('b', {}, a.title), h('span', {class: 'small muted'}, a.detail), h('div', {}, h('a', {href: a.route, class: 'small'}, 'Open →')))))) : h('p', {class: 'muted', style: {marginTop: '10px'}}, 'Nothing needs attention right now.'),
          d.case && d.case.history.some(x => x.type === 'PROBLEM_CHANGED') ? whatChanged(d.case.history) : null)),
      h('section', {class: 'card', style: {marginTop: '16px'}, 'aria-labelledby': 'h-up'}, h('h2', {id: 'h-up'}, 'Upcoming money movements'), h('p', {class: 'muted small'}, 'Confirmed obligations. Receivables become cash only when the bank observes them.'),
        h('div', {style: {marginTop: '10px'}}, obligationsTable(d.upcoming))));
  }
  function whatChanged(history) {
    const changes = history.filter(x => x.type === 'PROBLEM_CHANGED').slice(-3).reverse();
    return h('div', {style: {marginTop: '14px'}}, h('h3', {}, 'What changed'), h('ul', {class: 'reasons'}, changes.map(c => h('li', {}, UI.real(c.at) + ' — ' + (c.summary || 'Data changed')))));
  }
  function obligationsTable(rows) {
    return table(['Counterparty', 'Type', 'Due', 'Status', 'Amount', ''], rows.map(o => [
      h('span', {}, o.party, h('br'), h('span', {class: 'small muted'}, /_debt$/.test(o.reference) ? 'Loan repayment' : o.reference)),
      o.kind === 'PAYABLE' ? 'Money out' : 'Money in',
      day(o.due_at),
      h('span', {class: 'row'}, o.overdue ? h('span', {class: 'badge bad'}, 'Overdue') : null, o.protected ? h('span', {class: 'badge'}, 'Protected') : null,
        o.kind === 'RECEIVABLE' ? h('span', {class: 'badge warn'}, 'Expected, not settled') : null, !o.overdue && o.kind === 'PAYABLE' && !o.protected ? h('span', {class: 'badge'}, 'Confirmed') : null),
      money(o.amount), sourceButton(o.source_id)]), {right: [4], empty: 'No open obligations.'});
  }
  function issueCard(d) {
    const p = d.problem;
    const cls = {GAP: '', OVERDUE: '', DATA_REVIEW: 'warn', UNKNOWN_PAYMENT: 'warn', STRESS_GAP: 'warn', PENDING_DECISION: 'info', IN_FLIGHT: 'info', NO_GAP: 'good', EMPTY: 'info'}[d.state];
    const kicker = {GAP: 'Decision needed · before ' + day(p.first_gap_at), OVERDUE: 'Overdue', DATA_REVIEW: 'Data needs review', UNKNOWN_PAYMENT: 'Operation status unknown', STRESS_GAP: 'Risk if a customer pays late',
      PENDING_DECISION: 'Waiting for your approval', IN_FLIGHT: 'In progress', NO_GAP: 'No gap detected', EMPTY: 'Get started'}[d.state];
    let title = d.headline, text = '';
    if (d.state === 'GAP') {
      title = `A ${p.need.display} gap needs a plan.`;
      const out = p.drivers.outflows, late = p.drivers.late_inflows;
      text = `${out.length} payment${out.length === 1 ? '' : 's'} (${out.map(o => o.party).join(', ')}) fall due before ${late.length ? late.map(l => l.party + "'s expected receipt on " + day(l.expected_at)).join(', ') : 'any expected receipt'}. Cash would drop to ${p.minimum.display}; the amount includes your ${d.metrics.reserve.display} hard reserve.`;
    } else if (d.state === 'STRESS_GAP') {
      const s = p.stress.find(x => x.first_gap_at);
      text = s ? `On contract dates you keep the reserve. If the customer pays late (${s.scenario_id}), cash falls to ${s.minimum.display} on ${day(s.first_gap_at)}.` : '';
    } else if (d.state === 'NO_GAP') {
      text = 'No cash gap in the contract-date and DEMO delay scenarios for the known obligations. This is not a guarantee about the business.';
    } else if (d.state === 'UNKNOWN_PAYMENT') {
      text = 'The sandbox response was lost. The payment may already exist, so funds stay reserved and nothing is sent again until its status is found by the original key.';
    } else if (d.state === 'PENDING_DECISION' && d.next_review) {
      text = `${d.next_review.title} is due ${day(d.next_review.due_at)}. Approving it covers only this one action.`;
    } else if (d.state === 'DATA_REVIEW') {
      text = 'Some imported rows are unresolved. Plans and payments stay blocked until they are reviewed. Flags: ' + d.quality_flags.join(', ');
    } else if (d.state === 'OVERDUE') {
      text = 'An obligation is past its due date and still unpaid.';
    } else if (d.state === 'IN_FLIGHT') {
      text = 'An approved operation is reserved or sent. It counts as paid only after reconciliation.';
    }
    const actions = [h('a', {class: 'btn primary', href: d.cta.route}, d.cta.label)];
    if (d.state === 'GAP') actions.push(h('button', {class: 'btn', type: 'button', onclick: () => explainGap(d)}, `Why ${p.need.display}?`));
    return h('section', {class: 'card issue ' + cls, 'aria-labelledby': 'issue-title'}, h('div', {class: 'kicker'}, kicker), h('h2', {id: 'issue-title'}, title), text ? h('p', {}, text) : null, h('div', {class: 'row actions'}, actions));
  }
  function explainGap(d) {
    const p = d.problem;
    const rows = [...p.drivers.outflows.map(o => [day(o.at), o.party + (o.protected ? ' (protected)' : ''), '−' + o.amount.display, sourceButton(o.source_id)]),
      ...p.drivers.late_inflows.map(i => [day(i.expected_at), i.party + ' · expected, not settled', '+' + i.amount.display, sourceButton(i.source_id)])];
    Dialog.open(h('div', {class: 'head'}, h('h2', {id: 'dialog-title'}, 'Why ' + p.need.display + '?'), Dialog.close()),
      h('div', {class: 'body stack'},
        h('dl', {class: 'kv'}, h('dt', {}, 'Confirmed cash today'), h('dd', {}, d.metrics.confirmed_cash.display), h('dt', {}, 'Lowest cash on contract dates'), h('dd', {}, p.minimum.display + ' on ' + day(p.first_gap_at)),
          h('dt', {}, 'Hard reserve'), h('dd', {}, d.metrics.reserve.display), h('dt', {}, 'Need = reserve − lowest cash'), h('dd', {}, p.need.display)),
        table(['Date', 'Movement', 'Amount', ''], rows, {right: [2]}),
        h('p', {class: 'small muted'}, 'Computed by the server forecast (snapshot ' + d.snapshot_id.slice(0, 18) + '…). Payments are counted before receipts at the same time.')),
      h('div', {class: 'foot'}, h('a', {class: 'btn primary', href: '#case', onclick: () => Dialog.dismiss()}, 'Compare ways to cover it')));
  }

  /* ---------------------------------------------------------------- Case / Plans */
  let chartOption = null;
  async function casePage(main) {
    const [c] = await Promise.all([api('/v1/case'), App.refreshHome()]);
    App.state.caseData = c;
    if (!c.case) {
      put(main, head('Plans', 'Cover a cash gap with a validated plan.'), h('div', {class: 'card empty'}, h('h2', {}, 'No cash gap or overdue payment in the current data'), h('p', {}, c.message), h('p', {}, h('a', {href: '#money'}, 'Explore what-if scenarios →'))),
        c.last_closed ? h('section', {class: 'card'}, h('h2', {}, 'Last financial task'), h('p', {}, h('span', {class: 'badge ' + (c.last_closed.closed_reason === 'RESOLVED_SETTLED_AND_RECONCILED' ? 'good' : '')}, c.last_closed.closed_reason === 'RESOLVED_SETTLED_AND_RECONCILED' ? 'Resolved · settled and reconciled' : 'Closed · no longer detected in data')),
          h('ul', {class: 'reasons', style: {marginTop: '8px'}}, c.last_closed.history.slice().reverse().map(x => h('li', {}, UI.real(x.at) + ' · ' + x.type.replace(/_/g, ' ').toLowerCase() + (x.summary ? ' — ' + x.summary : ''))))) : null);
      return;
    }
    const p = c.problem, opts = c.options, plan = c.plan;
    const step = plan ? (plan.steps.some(s => s.status !== 'NOT_APPROVED') ? 4 : 3) : opts ? 2 : 1;
    const stepper = h('ol', {class: 'stepper', 'aria-label': 'Progress'}, ['Understand the gap', 'Compare options', 'Review exact action', 'Track the result'].map((t, i) =>
      h('li', {class: i + 1 < step ? 'done' : '', 'aria-current': i + 1 === step ? 'step' : null}, `${i + 1} · ${t}`)));
    const selectedCard = opts && c.selected ? opts.options.find(o => o.key === c.selected.key) : null;
    const showCard = opts ? opts.options.find(o => o.key === (chartOption || (selectedCard && selectedCard.key) || opts.lowest_cost_key)) : null;
    const baseline = c.chart.series.find(s => s.scenario_id === 'f0');
    const series = [{name: 'Keep current dates (no new action)', color: COLORS.f0, points: baseline.points}];
    if (showCard && showCard.path) series.push({name: showCard.label + ' (plan)', color: COLORS.plan, points: [baseline.points[0], ...showCard.path]});
    put(main, 
      head('Plans', p.first_gap_at ? `Cover the cash gap before ${day(p.first_gap_at)}. Choose a plan with its conditions in view.` : 'Resolve the open financial task.',
        h('button', {class: 'btn', type: 'button', onclick: () => Copilot.open({case_id: c.case.case_id, route: '#case'}, 'Why is there a gap, and what are my options?')}, 'Ask Copilot about this')),
      stepper,
      h('section', {class: 'card', 'aria-labelledby': 'h-gap'}, h('h2', {id: 'h-gap'}, '1 · The gap'),
        plan && plan.status !== 'NOT_STARTED' && c.case.history.length ? h('p', {class: 'notice', style: {marginTop: '8px'}}, 'At the start of this task: ' + (c.case.history[0].summary || '') + '. Below is the current data while the selected plan executes.') : null,
        h('div', {class: 'grid g4', style: {marginTop: '12px'}}, metric('Need', p.need, 'Includes the hard reserve', p.need.minor > 0), metric('First gap', {display: day(p.first_gap_at)}, 'Contract dates'),
          metric('Lowest cash', p.minimum, 'No new action', p.minimum.minor < p.reserve.minor), metric('Hard reserve', p.reserve, 'Policy minimum')),
        h('div', {class: 'grid g2', style: {marginTop: '14px'}},
          h('div', {}, h('h3', {}, 'Due before the gap'), table(['Date', 'Payment', 'Amount', ''], p.drivers.outflows.map(o => [day(o.at), h('span', {}, o.party, o.protected ? h('span', {class: 'badge', style: {marginLeft: '6px'}}, 'Protected') : null), o.amount.display, sourceButton(o.source_id)]), {right: [2], empty: 'No gap on contract dates.'})),
          h('div', {}, h('h3', {}, 'Arrives after the gap'), table(['Expected', 'Receipt', 'Amount', ''], p.drivers.late_inflows.map(o => [day(o.expected_at), h('span', {}, o.party, h('span', {class: 'badge warn', style: {marginLeft: '6px'}}, 'Expected, not settled')), o.amount.display, sourceButton(o.source_id)]), {right: [2], empty: 'No expected receipts after the gap.'}))),
        h('div', {class: 'grid g2', style: {marginTop: '14px'}}, h('div', {}, h('h3', {}, 'Known'), h('ul', {class: 'reasons'}, c.known.map(k => h('li', {}, k)))), h('div', {}, h('h3', {}, 'Not known'), h('ul', {class: 'reasons'}, c.unknown.map(k => h('li', {}, k))))),
        h('div', {style: {marginTop: '14px'}}, chart(series, p.reserve, {label: 'Cash before and after the selected option'}))),
      optionsSection(c),
      plan ? planSection(plan) : null,
      h('section', {class: 'card', 'aria-labelledby': 'h-hist'}, h('h2', {id: 'h-hist'}, 'History of this task'),
        h('ul', {class: 'reasons', style: {marginTop: '8px'}}, c.case.history.slice().reverse().map(x => h('li', {}, UI.real(x.at) + ' · ' + x.type.replace(/_/g, ' ').toLowerCase() + (x.summary ? ' — ' + x.summary : ''))))));
  }
  function optionsSection(c) {
    const opts = c.options;
    const target = h('input', {id: 'reserve-target', inputmode: 'decimal', placeholder: 'e.g. 25000', 'aria-describedby': 'target-help'});
    const compute = h('button', {class: 'btn primary', type: 'button', disabled: !can(['OWNER', 'ACCOUNTANT']), onclick: guard(async () => {
      const value = target.value.trim() ? {reserve_target_minor: UI.parseMajor(target.value)} : {};
      toast('Computing options with OR-Tools and the independent validator…');
      await api('/v1/case/options', value); chartOption = null; await App.render();
      toast('Options computed for the current snapshot.', 'good');
    })}, opts ? 'Recompute options' : 'Compare options');
    const intro = h('div', {class: 'row between'}, h('div', {}, h('h2', {id: 'h-opt'}, '2 · Options'), h('p', {class: 'muted small'}, opts ? opts.note + ' ' + opts.summary + '.' : 'Compute validated alternatives for the current data.')),
      h('div', {class: 'row'}, h('label', {class: 'small', for: 'reserve-target'}, 'Higher cushion target (CNY)', target), compute));
    const nodes = [intro, h('p', {id: 'target-help', class: 'small muted'}, 'Optional: the "Keep at least …" option uses this cash target; default is 125% of the hard reserve.')];
    const executing = c.plan && c.plan.status !== 'NOT_STARTED';
    if (c.options_stale && executing) nodes.push(h('div', {class: 'notice'}, 'The selected plan is being executed, so current data differs from the snapshot used to compare options. Recompute only if you want to change course; each remaining action is re-checked against current facts before approval.'));
    else if (c.options_stale) nodes.push(h('div', {class: 'notice warn', role: 'alert'}, 'Data changed since these options were computed. Recompute before choosing.'));
    if (opts) nodes.push(h('div', {class: 'options', style: {marginTop: '14px'}}, opts.options.map(o => optionCard(o, c, opts.lowest_cost_key))));
    nodes.push(extensionForm());
    return h('section', {class: 'card', 'aria-labelledby': 'h-opt'}, nodes);
  }
  function optionCard(o, c, lowest) {
    const selected = c.selected && c.selected.key === o.key;
    const dl = [];
    const add = (k, v) => dl.push(h('dt', {}, k), h('dd', {}, v));
    if (o.financing) {
      const f = o.financing;
      add('Net cash received', f.net.display); add('Gross principal', f.gross.display); add('Upfront fee', f.upfront_fee.display);
      add('Interest + repayment fee', UI.minorText({minor_str: String(BigInt(f.interest.minor_str) + BigInt(f.repayment_fee.minor_str))}));
      add('Repay', f.repayment.display + ' on ' + day(f.repay_at)); add('Total cost', f.total_cost.display);
      if (f.annual_cost) add('Effective cost', f.annual_cost.display + ' (cap ' + f.annual_cost.cap_display + ')');
      add('Money arrives', day(f.disburse_at)); add('Offer valid until', time(f.quote_expires_at));
    } else if (o.status === 'EXECUTABLE') add('New debt', 'CNY 0.00');
    if (o.status === 'EXECUTABLE') {
      const f0 = o.scenarios.find(s => s.scenario_id === 'f0');
      add('Lowest cash (contract dates)', f0 ? f0.minimum.display : '—');
    }
    if (o.reserve_target) add('Cash target', o.reserve_target.display);
    if (o.status === 'CONDITIONAL') {
      add('Proposed new due date', day(o.proposed_due_at));
      if (o.if_confirmed) add('If confirmed', ['OPTIMAL', 'FEASIBLE'].includes(o.if_confirmed.solver_status) ? 'Feasible without new debt' : 'Still not feasible');
    }
    const scen = o.scenarios ? h('div', {class: 'scen', 'aria-label': 'Scenario checks'}, o.scenarios.map(s => h('span', {class: 'badge ' + (s.holds ? 'good' : 'bad'), title: (s.validated ? 'Required and validated: ' : 'Checked for information: ') + s.minimum.display},
      (s.holds ? '✓ ' : '✗ ') + s.scenario_id + (s.validated ? '' : ' (info)')))) : null;
    const foot = [];
    if (o.status === 'EXECUTABLE') {
      foot.push(h('button', {class: 'btn ' + (selected ? '' : 'primary'), type: 'button', disabled: selected || !can(['OWNER', 'ACCOUNTANT']) || c.options_stale,
        onclick: guard(async () => { await api('/v1/case/select', {key: o.key}); toast('Plan selected. Review its first action when it is due.', 'good'); await App.render(); })}, selected ? 'Selected plan' : 'Choose this plan'));
      foot.push(h('button', {class: 'btn link small', type: 'button', onclick: () => { chartOption = o.key; App.render(); }}, 'Show on chart'));
    }
    if (o.status === 'CONDITIONAL') {
      foot.push(h('button', {class: 'btn small', type: 'button', disabled: !can(['OWNER']), onclick: guard(async () => {
        await api('/v1/demo/extension-decision', {request_id: o.request_id, accepted: true}); toast('Sandbox counterparty accepted; facts changed. Recompute the options.', 'good'); await App.render(); })}, 'Sandbox: supplier accepts'));
      foot.push(h('button', {class: 'btn small', type: 'button', disabled: !can(['OWNER']), onclick: guard(async () => {
        await api('/v1/demo/extension-decision', {request_id: o.request_id, accepted: false}); toast('Sandbox counterparty declined; original terms stay.', 'warn'); await App.render(); })}, 'Sandbox: supplier declines'));
    }
    return h('article', {class: 'option' + (selected ? ' selected' : ''), 'aria-label': o.label},
      h('div', {class: 'row between'}, statusBadge(o.status), o.key === lowest ? h('span', {class: 'badge blue'}, 'Lowest cost executable') : null),
      h('h3', {}, o.label), h('p', {class: 'small muted'}, o.summary),
      dl.length ? h('dl', {}, dl) : null, scen,
      o.warnings ? h('div', {class: 'notice warn small'}, o.warnings.join(' ')) : null,
      o.reasons ? h('div', {}, h('p', {class: 'small muted'}, o.reasons_label), h('ul', {class: 'reasons'}, o.reasons.map(r => h('li', {}, r.text)))) : null,
      o.objective_implemented ? h('details', {}, h('summary', {class: 'small'}, 'How this was computed'), h('p', {class: 'small'}, o.objective_implemented),
        h('p', {class: 'small muted'}, o.scope_note + ' Candidates checked: ' + (o.candidate_count || '—') + '. Required scenarios: ' + (o.validated_scenarios || []).join(', ') + '.')) : null,
      h('div', {class: 'foot'}, foot));
  }
  function extensionForm() {
    const payables = (App.state.home ? App.state.home.upcoming : []).filter(o => o.kind === 'PAYABLE' && !o.protected);
    if (!payables.length || !can(['OWNER', 'ACCOUNTANT'])) return null;
    const sel = h('select', {id: 'ext-ob'}, payables.map(o => h('option', {value: o.fact_id}, o.party + ' · ' + o.amount.display + ' · due ' + day(o.due_at))));
    const date = h('input', {id: 'ext-date', type: 'date', required: true});
    return h('details', {style: {marginTop: '14px'}}, h('summary', {}, 'Ask a supplier for more time (conditional option)'),
      h('p', {class: 'small muted'}, 'Creates a request only. The confirmed due date changes only after the counterparty’s decision is observed. Protected payments (payroll, rent) cannot be moved.'),
      h('div', {class: 'form-row'}, h('label', {for: 'ext-ob'}, 'Payable', sel), h('label', {for: 'ext-date'}, 'Proposed due date', date),
        h('button', {class: 'btn', type: 'button', onclick: guard(async () => {
          if (!date.value) throw new Error('Choose a proposed date');
          await api('/v1/extensions', {fact_id: sel.value, due_at: date.value + 'T00:00:00+08:00'});
          await api('/v1/case/options', {}); toast('Request saved as a conditional option.', 'good'); await App.render();
        })}, 'Create request')));
  }
  function planSection(plan) {
    /* Only the next action awaiting approval is emphasised; later ones stay reviewable but quiet. */
    const next = plan.steps.find(s => s.status === 'NOT_APPROVED');
    const rows = plan.steps.map(s => [day(s.at), s.title, statusBadge(s.status),
      s.status === 'NOT_APPROVED' ? h('a', {class: 'btn small' + (s === next ? ' primary' : ''), href: `#review/${plan.plan_id}/${s.action_id}`}, 'Review') : h('a', {class: 'btn small', href: '#activity/' + s.action_id}, 'Track')]);
    return h('section', {class: 'card', 'aria-labelledby': 'h-plan'},
      h('div', {class: 'row between'}, h('div', {}, h('h2', {id: 'h-plan'}, '3 · Selected plan'), h('p', {class: 'small muted'}, `${plan.settled} of ${plan.total} actions settled and reconciled. Each action needs its own exact approval when it is due.`)),
        can(['OWNER', 'ADMIN']) ? h('button', {class: 'btn small', type: 'button', onclick: guard(async () => { await api('/v1/demo/advance', {}); toast('Sandbox clock advanced / pending operations settled.'); await App.render(); })}, 'Sandbox: advance clock') : null),
      plan.cancelled ? h('div', {class: 'notice warn'}, 'Plan cancelled: no future sends. Sent operations are still tracked.') : null,
      h('div', {style: {marginTop: '10px'}}, table(['Due', 'Action', 'Status', ''], rows)),
      can(['OWNER']) && !plan.cancelled ? h('details', {style: {marginTop: '10px'}}, h('summary', {class: 'small'}, 'Stop future sends of this plan'),
        h('p', {class: 'small muted'}, 'Cancelling stops actions that are not yet sent. It cannot recall operations already sent.'),
        h('button', {class: 'btn danger small', type: 'button', onclick: guard(async () => { await api('/v1/plans/' + plan.plan_id + '/cancel', {}); toast('Future sends cancelled.', 'warn'); await App.render(); })}, 'Cancel future sends')) : null);
  }

  /* ---------------------------------------------------------------- Review dialog */
  async function review(planId, actionId) {
    const r = await api(`/v1/review/${encodeURIComponent(planId)}/${encodeURIComponent(actionId)}`);
    const confirm = h('input', {type: 'checkbox', id: 'confirm-exact'});
    const lost = h('input', {type: 'checkbox', id: 'lost'});
    const reauth = h('input', {type: 'password', id: 'approve-reauth', autocomplete: 'off', placeholder: 'Owner access token'});
    const approve = h('button', {class: 'btn primary', type: 'button', disabled: true, onclick: guard(async () => {
      const secret = reauth.value; reauth.value = '';
      const result = await api(`/v1/review/${encodeURIComponent(planId)}/${encodeURIComponent(actionId)}/approve`, {payload_hash: r.payload_hash, confirm: true, reauth: secret, inject_lost_response: lost.checked});
      Dialog.dismiss(); toast('Approved and queued. Track it until it is reconciled.', 'good'); location.hash = '#activity/' + result.action_id;
    })}, r.button || 'Approve');
    const sync = () => { approve.disabled = !confirm.checked || !r.approvable || !reauth.value; };
    confirm.addEventListener('change', sync); reauth.addEventListener('input', sync);
    const lt = r.loan_terms;
    const terms = lt ? h('div', {class: 'card', style: {padding: '14px'}}, h('h3', {}, 'Loan terms · ' + lt.product),
      h('dl', {class: 'kv', style: {marginTop: '8px'}}, ...[['Gross principal', lt.gross], ['Net cash received', lt.net], ['Upfront fee', lt.upfront_fee], ['Interest', lt.interest], ['Repayment fee', lt.repayment_fee], ['Repayment', lt.repayment]].flatMap(([k, v]) => [h('dt', {}, k), h('dd', {}, v.display)]),
        h('dt', {}, 'Repay on'), h('dd', {}, day(lt.repay_at)), lt.annual_cost ? h('dt', {}, 'Effective cost') : null, lt.annual_cost ? h('dd', {}, lt.annual_cost.display) : null, h('dt', {}, 'Quote valid until'), h('dd', {}, time(lt.quote_expires_at))), h('p', {class: 'small muted'}, lt.binding)) : null;
    Dialog.open(
      h('div', {class: 'head'}, h('div', {}, h('p', {class: 'small muted'}, 'Review exact action'), h('h2', {id: 'dialog-title'}, r.title)), Dialog.close()),
      h('div', {class: 'body stack'},
        h('div', {class: 'big num'}, r.amount.display),
        r.block ? h('div', {class: 'notice warn', role: 'alert'}, r.block.text) : null,
        h('dl', {class: 'kv'}, h('dt', {}, 'Recipient'), h('dd', {}, r.recipient.name, ' ', r.recipient.verified ? h('span', {class: 'badge good'}, 'Verified') : h('span', {class: 'badge bad'}, 'Not verified')),
          h('dt', {}, 'Due'), h('dd', {}, day(r.due_at)), h('dt', {}, 'Account'), h('dd', {}, 'Operating account · CNY'),
          h('dt', {}, 'Available now'), h('dd', {}, r.available_now.display), h('dt', {}, 'After this action'), h('dd', {}, r.available_after.display), h('dt', {}, 'Hard reserve'), h('dd', {}, r.reserve.display)),
        terms,
        h('p', {class: 'notice'}, r.scope),
        h('div', {class: 'grid g2'}, h('div', {}, h('h3', {}, 'Approving means'), h('ul', {class: 'reasons'}, r.approval_means.map(x => h('li', {}, x)))),
          h('div', {}, h('h3', {}, 'It does not mean'), h('ul', {class: 'reasons'}, r.approval_does_not_mean.map(x => h('li', {}, x))))),
        r.approvable ? h('label', {class: 'check', for: 'confirm-exact'}, confirm, `I approve exactly this ${r.kind === 'DRAW_LOAN' ? 'loan draw' : r.kind === 'REPAY_LOAN' ? 'loan repayment' : 'payment'} of ${r.amount.display} to ${r.recipient.name}.`) : null,
        r.approvable ? h('label', {for: 'approve-reauth'}, 'Confirm it is you: re-enter your owner access token', reauth) : null,
        r.command ? h('details', {}, h('summary', {class: 'small'}, 'Command, versions and hash'), h('p', {class: 'small muted'}, 'payload SHA-256 ' + r.payload_hash), h('pre', {}, JSON.stringify(r.command, null, 2))) : null,
        r.approvable ? h('details', {}, h('summary', {class: 'small'}, 'Sandbox test controls'), h('label', {class: 'check', for: 'lost'}, lost, 'Simulate a lost sandbox response for this send (tests UNKNOWN recovery; no double payment).')) : null),
      h('div', {class: 'foot'}, h('button', {class: 'btn', type: 'button', onclick: () => Dialog.dismiss()}, r.approvable ? 'Not now' : 'Close'), r.approvable ? approve : null));
  }

  /* ---------------------------------------------------------------- Money */
  let scenarioPick = 'f0';
  async function moneyPage(main) {
    const d = await App.refreshHome();
    const picks = [['f0', 'On contract dates'], ['delay_5', 'Customer 5 days late'], ['delay_25', 'Customer 25 days late']];
    const radios = h('div', {class: 'row', role: 'radiogroup', 'aria-label': 'Scenario'}, picks.map(([k, t]) => h('button', {class: 'btn small' + (scenarioPick === k ? ' primary' : ''), type: 'button', role: 'radio', 'aria-checked': String(scenarioPick === k), onclick: () => { scenarioPick = k; App.render(); }}, t)));
    const s = d.chart.series.find(x => x.scenario_id === scenarioPick);
    const stress = d.problem.stress.find(x => x.scenario_id === scenarioPick);
    const receivables = d.upcoming.filter(o => o.kind === 'RECEIVABLE');
    const ob = h('select', {id: 'wi-ob'}, receivables.map(o => h('option', {value: o.reference}, o.party + ' · ' + o.amount.display + ' · expected ' + day(o.due_at))));
    const delay = h('input', {id: 'wi-delay', type: 'number', min: 0, max: 365, value: 10});
    const pct = h('input', {id: 'wi-pct', type: 'number', min: 0, max: 100, value: 100});
    const out = h('div', {'aria-live': 'polite'});
    put(main, 
      head('Money', 'Explore timing and assumptions. What-if keeps actual facts unchanged.'),
      h('section', {class: 'card', 'aria-labelledby': 'h-fc'}, h('div', {class: 'row between'}, h('h2', {id: 'h-fc'}, 'Cash forecast'), radios),
        h('p', {class: 'muted small'}, 'Expected, not settled. Lowest cash ' + (scenarioPick === 'f0' ? d.problem.minimum.display : (stress ? stress.minimum.display : '—')) + '. DEMO scenarios are uncalibrated.'),
        chart([{name: picks.find(x => x[0] === scenarioPick)[1], color: COLORS[scenarioPick], points: s.points}], d.chart.reserve)),
      h('section', {class: 'card', 'aria-labelledby': 'h-wi'}, h('h2', {id: 'h-wi'}, 'What-if for one receivable'), h('p', {class: 'muted small'}, 'Change one customer payment. Scenario only — keeps actual facts unchanged and creates no executable plan.'),
        receivables.length ? h('div', {class: 'form-row', style: {marginTop: '10px'}}, h('label', {for: 'wi-ob'}, 'Receivable', ob), h('label', {for: 'wi-delay'}, 'Extra delay (days)', delay), h('label', {for: 'wi-pct'}, 'Received on that date (%)', pct),
          h('button', {class: 'btn primary', type: 'button', onclick: guard(async () => {
            const bps = Math.round(Number(pct.value) * 100);
            const r = await api('/v1/case/what-if', {obligation_id: ob.value, delay_days: Number(delay.value), receipt_bps: bps});
            out.replaceChildren(h('div', {class: 'notice warn', style: {marginTop: '12px'}}, r.label),
              h('div', {class: 'grid g3', style: {marginTop: '12px'}}, metric('Lowest cash now', r.baseline.minimum, 'Contract dates', r.baseline.minimum.minor < d.metrics.reserve.minor),
                metric('Lowest cash in scenario', r.scenario.minimum, r.scenario.first_gap_at ? 'Gap from ' + day(r.scenario.first_gap_at) : 'No gap', r.scenario.minimum.minor < d.metrics.reserve.minor), metric('Need in scenario', r.scenario.need, 'Includes the reserve')),
              r.selected_plan ? h('p', {class: 'notice ' + (r.selected_plan.holds ? 'good' : 'bad'), style: {marginTop: '10px'}}, 'Your selected plan ' + (r.selected_plan.holds ? 'still keeps' : 'would NOT keep') + ' the reserve in this scenario (lowest ' + r.selected_plan.minimum.display + ').') : null,
              h('p', {class: 'small muted', style: {marginTop: '8px'}}, 'Hypothetical lowest-cost plan for this scenario: ' + r.hypothetical_min_cost.solver_status + (r.hypothetical_min_cost.total_cost ? ' · cost ' + r.hypothetical_min_cost.total_cost.display : '') + ' (not executable).'),
              chart([{name: 'Contract dates', color: COLORS.f0, points: r.chart.series[0].points}, {name: 'What-if', color: COLORS.what_if, dash: '5 4', points: r.chart.series[1].points}], r.chart.reserve));
          })}, 'Calculate scenario')) : h('p', {class: 'muted'}, 'No open receivables.'), out),
      h('div', {class: 'split'},
        h('section', {class: 'card'}, h('h2', {}, 'Money in and out'), h('div', {style: {marginTop: '10px'}}, obligationsTable(d.upcoming))),
        h('section', {class: 'card'}, h('h2', {}, 'Settled cash movements'), h('p', {class: 'muted small'}, 'Observed by the sandbox bank or imported statements.'),
          h('div', {style: {marginTop: '10px'}}, table(['Date', 'Movement', 'Amount', ''], d.transactions.map(t => [day(t.at), t.status === 'SETTLED' ? (t.party || t.reference) : 'Opening balance', t.amount.display, sourceButton(t.source_id)]), {right: [2], empty: 'No settled movements.'})))));
  }

  /* ---------------------------------------------------------------- Activity */
  async function activity(main, actionId) {
    if (actionId) return operation(main, actionId);
    const a = await api('/v1/activity');
    const recon = a.reconciliation;
    put(main, head('Activity', 'What is waiting for you and what has actually happened.'),
      a.stopped ? h('div', {class: 'notice warn', role: 'alert'}, 'New sends are stopped. Status checks and reconciliation still run.') : null,
      h('div', {class: 'split'},
        h('section', {class: 'card'}, h('h2', {}, 'Operations'), h('div', {style: {marginTop: '10px'}}, table(['Action', 'Due', 'Status', ''], a.operations.map(o => [o.title, day(o.due_at), statusBadge(o.status), h('a', {href: '#activity/' + o.action_id, class: 'btn small'}, 'Open')]), {empty: 'No approved operations yet. Approve a due action from Plans.'}))),
        h('section', {class: 'card'}, h('h2', {}, 'Last reconciliation'),
          recon ? h('dl', {class: 'kv', style: {marginTop: '10px'}}, h('dt', {}, 'Status'), h('dd', {}, h('span', {class: 'badge ' + (recon.matched ? 'good' : 'bad')}, recon.status)), h('dt', {}, 'Local cash'), h('dd', {}, UI.minorText(recon.local_cash_minor)),
            h('dt', {}, 'Sandbox cash'), h('dd', {}, UI.minorText(recon.provider_cash_minor)), h('dt', {}, 'Difference'), h('dd', {}, UI.minorText(recon.discrepancy_minor)), h('dt', {}, 'Business time'), h('dd', {}, time(recon.at))) : h('p', {class: 'muted'}, 'Not reconciled yet.'),
          h('button', {class: 'btn small', type: 'button', style: {marginTop: '10px'}, disabled: !can(['OWNER', 'ACCOUNTANT', 'ADMIN']), title: can(['OWNER', 'ACCOUNTANT', 'ADMIN']) ? '' : 'Auditors read reconciliations; they do not run them', onclick: guard(async () => { const r = await api('/v1/reconcile', {}); toast('Reconciliation: ' + r.status, r.matched ? 'good' : 'bad'); await App.render(); })}, 'Refresh & reconcile'))),
      h('section', {class: 'card', style: {marginTop: '16px'}}, h('h2', {}, 'Journal'), h('ul', {class: 'reasons', style: {marginTop: '10px'}}, a.events.map(e => h('li', {}, UI.real(e.at) + ' · ' + e.label + (e.repeats > 1 ? (e.type.startsWith('action.') ? ` (status re-checked ${e.repeats}× until ${UI.real(e.last_at)})` : ` (×${e.repeats})`) : ''))))));
  }
  async function operation(main, actionId) {
    const t = await api('/v1/timeline/' + encodeURIComponent(actionId));
    const current = t.steps.findIndex(s => !s.done);
    const tone = t.status === 'UNKNOWN' ? 'warn' : t.status === 'SETTLED' ? 'good' : t.status === 'FAILED' ? 'bad' : '';
    put(main, head(t.title, 'Operation timeline. Only observed transitions are shown.', h('a', {class: 'btn', href: '#activity'}, '← All activity')),
      h('div', {class: 'split'},
        h('section', {class: 'card'}, h('div', {class: 'row between'}, h('h2', {}, 'Status'), statusBadge(t.status)), h('p', {class: 'notice ' + tone, style: {margin: '12px 0'}}, t.message),
          h('ol', {class: 'timeline'}, t.steps.map((s, i) => h('li', {class: s.done ? 'done' : i === current ? (t.status === 'UNKNOWN' ? 'warn' : 'current') : ''}, h('b', {}, s.label), h('br'),
            h('span', {class: 'small muted'}, s.done ? 'Observed ' + UI.real(s.observed_at) : i === current ? (t.status === 'UNKNOWN' ? 'Waiting: status lookup by the original key' : 'Waiting') : 'Not yet')))),
          t.can_check_status ? h('div', {class: 'stack'}, h('button', {class: 'btn', type: 'button', onclick: guard(async () => { await api('/v1/actions/' + encodeURIComponent(actionId) + '/recover', {}); await App.render(); })}, 'Check status (same key)'), h('p', {class: 'small muted'}, t.check_status_note)) : null),
        h('section', {class: 'card'}, h('h2', {}, 'Details'), h('dl', {class: 'kv', style: {marginTop: '10px'}}, h('dt', {}, 'Amount'), h('dd', {}, UI.minorText(t.command.amount_minor)), h('dt', {}, 'Recipient version'), h('dd', {}, t.command.beneficiary_version_id), h('dt', {}, 'Due'), h('dd', {}, day(t.command.at)),
            h('dt', {}, 'Sandbox reference'), h('dd', {}, t.provider_ref || '—'), h('dt', {}, 'Send attempts'), h('dd', {}, String(t.attempts.length))),
          t.reconciliation ? h('p', {class: 'notice good', style: {marginTop: '10px'}}, 'Reconciled: local ' + UI.minorText(t.reconciliation.local_cash_minor) + ' = sandbox ' + UI.minorText(t.reconciliation.provider_cash_minor) + '.') : null,
          h('p', {style: {marginTop: '10px'}}, h('a', {href: '#case'}, 'Back to the plan →')),
          h('details', {}, h('summary', {class: 'small'}, 'Exact approved command'), h('pre', {}, JSON.stringify(t.command, null, 2))))));
    if (!['SETTLED', 'FAILED'].includes(t.status)) App.poll(() => location.hash === '#activity/' + actionId, 3000);
  }

  /* ---------------------------------------------------------------- Documents */
  const wizard = {template: 'obligations', file: null, preview: null, options: {}, mapping: null};
  async function documents(main) {
    const imports = await api('/v1/imports');
    put(main, head('Documents', 'Turn source records into reviewed financial facts.'),
      h('ol', {class: 'stepper', 'aria-label': 'Import steps'}, ['Add records', 'Map columns', 'Review issues', 'Use verified data'].map((t, i) => h('li', {'aria-current': i === (wizard.preview ? 2 : wizard.file ? 1 : 0) ? 'step' : null}, `${i + 1} · ${t}`))),
      importWizard(), reviewSection(imports), searchSection());
  }
  function importWizard() {
    const template = h('select', {id: 'imp-template'}, [['obligations', 'Invoices / obligations (pay or receive)'], ['transactions', 'Bank transactions (settled)']].map(([v, t]) => h('option', {value: v, selected: wizard.template === v}, t)));
    template.addEventListener('change', () => { wizard.template = template.value; wizard.mapping = null; if (wizard.file) runPreview(); else App.render(); });
    const file = h('input', {id: 'imp-file', type: 'file', class: 'sr-only', accept: '.csv,.xlsx,text/csv'});
    file.addEventListener('change', guard(async () => {
      const f = file.files[0]; if (!f) return; if (f.size > 1000000) throw new Error('Files up to 1 MB');
      const xlsx = /\.xlsx$/i.test(f.name);
      wizard.file = xlsx ? {name: f.name, format: 'xlsx', content_base64: await toBase64(f)} : {name: f.name, format: 'csv', content: await f.text()};
      wizard.mapping = null; await runPreview();
    }));
    const p = wizard.preview;
    const parts = [h('h2', {id: 'imp-h'}, 'Import records'), h('p', {class: 'muted small'}, 'CSV or XLSX (first sheet). Generic upload, not a bank connection. Amounts in CNY like 12,500.50; the server converts them exactly.'),
      h('div', {class: 'form-row', style: {marginTop: '10px', alignItems: 'start'}}, h('label', {for: 'imp-template'}, 'What is in the file?', template),
        h('div', {class: 'filepick'}, h('span', {class: 'lbl'}, 'File'), h('label', {for: 'imp-file', class: 'btn'}, file, wizard.file ? 'Choose another file' : 'Choose CSV or XLSX…'),
          h('span', {class: 'small muted'}, wizard.file ? wizard.file.name : 'No file selected · up to 1 MB')))];
    if (p) {
      const fields = Object.keys(p.mapping);
      const selects = fields.map(f => {
        const sel = h('select', {'data-field': f, id: 'map-' + f}, h('option', {value: ''}, '— not in file —'), p.headers.map(hd => h('option', {value: hd, selected: p.mapping[f] === hd}, hd)));
        sel.addEventListener('change', () => { wizard.mapping = Object.fromEntries(fields.map(x => [x, document.getElementById('map-' + x).value || null])); runPreview(); });
        const name = f.replace(/_/g, ' ');
        return h('label', {for: 'map-' + f}, name.charAt(0).toUpperCase() + name.slice(1), sel);
      });
      const opt = (id, label, values, key) => {
        const sel = h('select', {id}, values.map(([v, t]) => h('option', {value: v, selected: String(p.options[key] ?? '') === v}, t)));
        sel.addEventListener('change', () => { wizard.options[key] = sel.value === '' ? null : sel.value; runPreview(); });
        return h('label', {for: id}, label, sel);
      };
      parts.push(h('h3', {style: {marginTop: '16px'}}, 'Map columns'), h('div', {class: 'form-row'}, selects),
        h('div', {class: 'form-row', style: {marginTop: '10px'}}, opt('opt-dec', 'Decimal separator', [['.', 'Point · 12,500.50'], [',', 'Comma · 12.500,50']], 'decimal'),
          opt('opt-date', 'Date format', [['auto', 'Detect (ask if ambiguous)'], ['YYYY-MM-DD', 'YYYY-MM-DD'], ['DD.MM.YYYY', 'DD.MM.YYYY'], ['DD/MM/YYYY', 'DD/MM/YYYY'], ['MM/DD/YYYY', 'MM/DD/YYYY'], ['YYYY/MM/DD', 'YYYY/MM/DD'], ['YYYY年MM月DD日', 'YYYY年MM月DD日']], 'date_format'),
          p.template === 'obligations' ? opt('opt-kind', 'Type of all rows', [['', 'From a column'], ['PAYABLE', 'All are payables'], ['RECEIVABLE', 'All are receivables']], 'kind') : null,
          opt('opt-ns', 'Records namespace', [['upload_' + p.template, 'New upload'], ['synthetic_csv', 'Update records from the original statement']], 'namespace')),
        p.missing.length ? h('div', {class: 'notice warn', style: {marginTop: '10px'}}, 'Map before importing: ' + p.missing.join(', ')) : null,
        h('h3', {style: {marginTop: '16px'}}, `Preview · ${p.summary.ready} ready, ${p.summary.errors} need review, ${p.summary.updates} update existing records`),
        table(['Row', 'Status', 'Reference', 'Counterparty', p.template === 'obligations' ? 'Type · due' : 'Date', 'Amount', 'Notes'], p.rows.slice(0, 60).map(r => {
          const n = r.normalized;
          return [String(r.row),
            r.errors.length ? h('span', {class: 'badge bad'}, r.errors[0].code.replace(/_/g, ' ').toLowerCase()) : r.update ? h('span', {class: 'badge blue'}, 'Update v' + r.update.from_version + '→v' + n.version) : h('span', {class: 'badge good'}, 'Ready'),
            n ? n.external_id : '', n ? n.counterparty : '', n ? (p.template === 'obligations' ? (n.kind === 'PAYABLE' ? 'Pay' : 'Receive') + ' · ' + day(n.due_at) : day(n.event_time)) : '', r.display || '',
            [...r.errors.map(e => e.text), ...r.warnings, ...(r.update ? Object.keys(r.update.changes).map(k => k.replace('_minor', '').replace('_', ' ') + ' changes') : [])].join(' · ')];
        }), {right: [5]}),
        commitBlock(p));
    }
    return h('section', {class: 'card', 'aria-labelledby': 'imp-h'}, parts);
  }
  function commitBlock(p) {
    const ok = h('input', {type: 'checkbox', id: 'imp-ok'});
    const btn = h('button', {class: 'btn primary', type: 'button', disabled: true, onclick: guard(async () => {
      const r = await api('/v1/imports/commit', Object.assign(previewRequest(), {confirm: true, raw_digest: p.raw_digest}));
      wizard.preview = null; wizard.file = null; wizard.mapping = null; wizard.options = {};
      toast(`Imported: ${r.import.accepted} accepted, ${r.import.rejected} in review (${r.import.status}).`, r.import.rejected ? 'warn' : 'good'); await App.refreshHome(); await App.render();
    })}, `Import ${p.summary.ready} rows` + (p.summary.errors ? ` and send ${p.summary.errors} to review` : ''));
    ok.addEventListener('change', () => { btn.disabled = !ok.checked || p.missing.length > 0; });
    return h('div', {class: 'stack', style: {marginTop: '12px'}},
      p.template === 'transactions' ? h('p', {class: 'notice warn small'}, 'Settled transactions change confirmed cash. In this sandbox the simulator is the bank; movements it has not observed will cause a reconciliation mismatch and stop new sends.') : null,
      h('label', {class: 'check', for: 'imp-ok'}, ok, 'I checked the mapping, signs, dates and amounts above.'), h('div', {}, btn));
  }
  function previewRequest() {
    const f = wizard.file || {};
    return {template: wizard.template, mapping: wizard.mapping || undefined, options: wizard.options, format: f.format, content: f.content, content_base64: f.content_base64};
  }
  async function runPreview() { try { wizard.preview = await api('/v1/imports/preview', previewRequest()); } catch (e) { toast(e.message, 'bad'); wizard.preview = null; } App.render(); }
  function toBase64(file) { return new Promise((res, rej) => { const r = new FileReader(); r.onload = () => res(String(r.result).split(',')[1]); r.onerror = () => rej(new Error('Could not read the file')); r.readAsDataURL(file); }); }
  function reviewSection(data) {
    const batches = data.imports;
    const open = batches.filter(b => b.open_rows);
    return h('section', {class: 'card', 'aria-labelledby': 'rev-h'}, h('h2', {id: 'rev-h'}, 'Review issues'),
      h('p', {class: 'muted small'}, open.length ? `${open.length} import(s) have rows to review. Plans and payments stay blocked until they are resolved.` : 'No unresolved rows.'),
      h('div', {class: 'stack', style: {marginTop: '10px'}}, batches.slice().reverse().slice(0, 8).map(b => h('div', {class: 'task ' + (b.open_rows ? 'warning' : '')}, h('span', {class: 'sev', 'aria-hidden': 'true'}),
        h('div', {class: 'body'}, h('b', {}, `${b.accepted} row${b.accepted === 1 ? '' : 's'} accepted · ` + (b.open_rows ? `${b.open_rows} need${b.open_rows === 1 ? 's' : ''} a decision` : 'nothing to review')),
          h('span', {class: 'small muted'}, 'Import …' + b.import_id.slice(-8) + ' · ' + b.review_status.replace(/_/g, ' ').toLowerCase()),
          b.rows.filter(r => !r.decision).map(r => rowReview(b, r)))))));
  }
  function rowReview(batch, row) {
    if (row.raw && row.raw.kind === 'INVALID') {
      /* Row from the mapping wizard: the original problem is in its reference field. */
      let problems = []; try { problems = JSON.parse(row.raw.reference); } catch (_) { problems = []; }
      const reason = h('input', {placeholder: 'Reason (at least 5 characters)', minlength: 5, 'aria-label': 'Reason for discarding'});
      return h('details', {style: {marginTop: '8px'}, open: true}, h('summary', {class: 'small'}, `Uploaded row ${row.raw.external_id.replace('row_', '')} · needs a decision`),
        h('ul', {class: 'reasons'}, problems.map(e => h('li', {}, e.text + ' (' + e.code + ')'))),
        h('p', {class: 'small muted'}, 'Fix the source file and import it again with the right options, or discard this row with a reason. The original upload stays stored as evidence.'),
        h('div', {class: 'form-row'}, reason, h('button', {class: 'btn small', type: 'button', disabled: !can(['OWNER', 'ACCOUNTANT']), onclick: guard(async () => {
          await api('/v1/imports/' + batch.import_id + '/review', {row_number: row.row_number, decision: 'DISCARD', reason: reason.value});
          toast('Row discarded with its reason; the upload remains in the audit trail.', 'good'); await App.refreshHome(); await App.render();
        })}, 'Discard row')));
    }
    const fields = Object.keys(row.raw);
    const inputs = fields.map(f => h('label', {class: 'small'}, f, h('input', {'data-f': f, value: row.raw[f] ?? ''})));
    const reason = h('input', {placeholder: 'Reason (at least 5 characters)', minlength: 5, 'aria-label': 'Reason'});
    const decision = h('select', {'aria-label': 'Decision'}, h('option', {value: 'CORRECT'}, 'Correct and confirm a new version'), h('option', {value: 'DISCARD'}, 'Discard this row'));
    return h('details', {style: {marginTop: '8px'}}, h('summary', {class: 'small'}, `Row ${row.row_number} · ${row.code}`),
      h('div', {class: 'form-row', style: {marginTop: '8px'}}, inputs), h('div', {class: 'form-row', style: {marginTop: '8px'}}, decision, reason,
        h('button', {class: 'btn small', type: 'button', disabled: !can(['OWNER', 'ACCOUNTANT']), onclick: guard(async ev => {
          const box = ev.currentTarget.closest('details'); const corrected = {};
          box.querySelectorAll('input[data-f]').forEach(i => { corrected[i.dataset.f] = i.value; });
          await api('/v1/imports/' + batch.import_id + '/review', {row_number: row.row_number, decision: decision.value, reason: reason.value, corrected});
          toast('Review saved with its source and audit trail.', 'good'); await App.refreshHome(); await App.render();
        })}, 'Save decision')));
  }
  function searchSection() {
    const q = h('input', {id: 'doc-q', placeholder: 'Contract, customer, 合同…'});
    const out = h('div', {'aria-live': 'polite'});
    const title = h('input', {id: 'doc-title'}), text = h('textarea', {id: 'doc-text', placeholder: 'Paste a synthetic contract or note. It is stored as untrusted evidence.'});
    return h('section', {class: 'card', 'aria-labelledby': 'src-h'}, h('h2', {id: 'src-h'}, 'Evidence and documents'),
      h('div', {class: 'form-row', style: {marginTop: '10px'}}, h('label', {for: 'doc-q'}, 'Search sources (keyword match)', q), h('button', {class: 'btn', type: 'button', onclick: guard(async () => {
        const r = await api('/v1/retrieval', {query: q.value});
        out.replaceChildren(h('p', {class: 'small muted'}, r.mode + ' · ' + r.hits.length + ' fragments'), ...r.hits.map(x => h('div', {class: 'result'}, h('h4', {}, x.title + ' · v' + x.version + ' · line ' + x.line), h('p', {class: 'small'}, x.excerpt), sourceButton(x.source_id))));
      })}, 'Search')), out,
      h('details', {style: {marginTop: '12px'}}, h('summary', {}, 'Add a text document'), h('div', {class: 'stack', style: {marginTop: '8px'}}, h('label', {for: 'doc-title'}, 'Title', title), h('label', {for: 'doc-text'}, 'Text', text),
        h('button', {class: 'btn', type: 'button', onclick: guard(async () => { const r = await api('/v1/documents', {title: title.value, text: text.value, format: 'text'}); toast('Document stored: ' + r.status, 'good'); })}, 'Store document'))),
      h('p', {class: 'small muted', style: {marginTop: '10px'}}, 'Advanced tools (manual payment allocation, raw synthetic CSV import) remain in the ', h('a', {href: '/legacy'}, 'previous cabinet'), '.'));
  }

  /* ---------------------------------------------------------------- Settings */
  const up = v => h('span', {class: 'badge ' + (['CONNECTED', 'RUNNING', 'OK'].includes(v) ? 'good' : 'warn')}, v);
  async function settings(main) {
    const [st, health] = await Promise.all([api('/v1/settings'), api('/v1/health')]);
    const home = App.state.home || await App.refreshHome();
    const reserve = h('input', {id: 'set-reserve', inputmode: 'decimal', value: UI.minorText(st.policy.reserve_minor).replace('CNY ', '')});
    const prot = h('input', {id: 'set-prot', value: st.policy.protected.join(', ')});
    const reason = h('input', {id: 'stop-reason', placeholder: 'Reason'});
    put(main, head('Settings', 'Policy, controls and runtime information.'),
      h('div', {class: 'grid g2'},
        h('section', {class: 'card'}, h('h2', {}, 'Payment policy'), h('p', {class: 'small muted'}, 'Version ' + st.policy.version + '. Saving creates a new version and invalidates prior approvals.'),
          h('div', {class: 'stack', style: {marginTop: '10px'}}, h('label', {for: 'set-reserve'}, 'Hard reserve (CNY)', reserve), h('label', {for: 'set-prot'}, 'Protected obligations (references, comma separated)', prot),
            h('button', {class: 'btn primary', type: 'button', disabled: !can(['OWNER']), onclick: guard(async () => {
              await api('/v1/settings', {reserve_minor: UI.parseMajor(reserve.value), protected: prot.value.split(',').map(x => x.trim()).filter(Boolean)});
              toast('New policy version saved. Recompute options; re-approve due actions.', 'good'); await App.refreshHome(); await App.render(); })}, 'Save new policy version'))),
        h('section', {class: 'card'}, h('h2', {}, 'Send controls'), h('p', {class: 'small muted'}, home.stopped ? 'New sends are STOPPED.' : 'New sends are allowed. Stopping does not recall operations already sent.'),
          h('div', {class: 'form-row', style: {marginTop: '10px'}}, h('label', {for: 'stop-reason'}, 'Reason', reason),
            h('button', {class: 'btn danger', type: 'button', disabled: home.stopped ? !can(['OWNER']) : !can(['OWNER', 'ADMIN']), title: home.stopped && !can(['OWNER']) ? 'Only the owner can resume, after cash reconciles' : '', onclick: guard(async () => {
              const stop = !home.stopped; await api('/v1/controls/stop', {enabled: stop, reason: reason.value || (stop ? 'Owner stop from settings' : 'Owner resume from settings')});
              await App.refreshHome(); toast(stop ? 'New sends stopped.' : 'New sends resumed.', 'warn'); await App.render(); })}, home.stopped ? 'Resume new sends' : 'Stop new sends')),
          h('hr'), h('h3', {}, 'Sandbox controls'), h('p', {class: 'small muted'}, 'Moves the synthetic business clock to the next contract date and lets pending sandbox operations settle. Not available to the model.'),
          h('button', {class: 'btn', type: 'button', disabled: !can(['OWNER', 'ADMIN']), onclick: guard(async () => { await api('/v1/demo/advance', {}); await App.refreshHome(); toast('Sandbox clock advanced.'); await App.render(); })}, 'Advance sandbox clock'))),
      h('div', {class: 'grid g2', style: {marginTop: '16px'}},
        h('section', {class: 'card'}, h('h2', {}, 'Runtime'), h('dl', {class: 'kv', style: {marginTop: '10px'}}, h('dt', {}, 'Database'), h('dd', {}, health.database.backend + ' ', up(health.database.status)), h('dt', {}, 'Worker'), h('dd', {}, up(health.worker.status)), h('dt', {}, 'Sandbox'), h('dd', {}, up(health.simulator.status)),
          h('dt', {}, 'Model mode'), h('dd', {}, st.model.mode + (st.model.model ? ' · ' + st.model.model : '')), h('dt', {}, 'Model limits'), h('dd', {}, st.model.max_steps + ' steps · ' + st.model.max_elapsed_seconds + ' s')),
          h('p', {class: 'small muted', style: {marginTop: '10px'}}, st.model.mode === 'MOCK' ? 'MOCK is a deterministic offline fixture for integration tests; it does not understand arbitrary language.' : 'Live model output is narrative only; numbers come from tools.')),
        h('section', {class: 'card'}, h('h2', {}, 'Account'), h('dl', {class: 'kv', style: {marginTop: '10px'}}, h('dt', {}, 'Role'), h('dd', {}, App.state.role), h('dt', {}, 'Members'), h('dd', {}, st.memberships.map(m => m.user_id + ' (' + m.role + (m.active ? '' : ', inactive') + ')').join(', '))),
          h('div', {class: 'row', style: {marginTop: '12px'}}, h('button', {class: 'btn', type: 'button', onclick: guard(() => App.signOut())}, 'Sign out'), h('a', {class: 'btn link', href: '/legacy'}, 'Previous cabinet')))));
  }

  return {home, casePage, review, moneyPage, activity, documents, settings, evidence};
})();

/* Accessible modal dialog built on <dialog>: focus is trapped by showModal and restored on close. */
const Dialog = (() => {
  let opener = null;
  const el = () => document.getElementById('dialog');
  function open(...parts) {
    opener = document.activeElement;
    const d = el(); d.replaceChildren(...parts.filter(Boolean));
    d.onclose = () => {
      if (location.hash.startsWith('#review/')) history.replaceState(null, '', '#case');
      if (opener && opener.isConnected && opener.focus) opener.focus();
    };
    if (!d.open) d.showModal();
    const f = d.querySelector('.body input, .body button, .foot .btn'); (f || d).focus();
  }
  function dismiss() { const d = el(); if (d.open) d.close(); }
  function close() { return UI.h('button', {class: 'btn link', type: 'button', 'aria-label': 'Close dialog', onclick: dismiss}, '✕'); }
  return {open, dismiss, close};
})();
