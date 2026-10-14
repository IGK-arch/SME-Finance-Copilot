'use strict';
/* Shared UI helpers. Data is always inserted as text nodes, never as HTML. */
const UI = (() => {
  const TZ = 'Asia/Shanghai';
  function h(tag, attrs, ...kids) {
    const n = document.createElement(tag);
    for (const [k, v] of Object.entries(attrs || {})) {
      if (v === null || v === undefined || v === false) continue;
      if (k === 'class') n.className = v;
      else if (k === 'style' && typeof v === 'object') Object.assign(n.style, v); /* CSSOM: allowed by CSP */
      else if (k === 'text') n.textContent = v;
      else if (k.startsWith('on') && typeof v === 'function') n.addEventListener(k.slice(2), v);
      else if (v === true) n.setAttribute(k, '');
      else n.setAttribute(k, String(v));
    }
    for (const kid of kids.flat(Infinity)) {
      if (kid === null || kid === undefined || kid === false) continue;
      n.append(kid instanceof Node ? kid : document.createTextNode(String(kid)));
    }
    return n;
  }
  const svgNS = 'http://www.w3.org/2000/svg';
  function s(tag, attrs, ...kids) {
    const n = document.createElementNS(svgNS, tag);
    for (const [k, v] of Object.entries(attrs || {})) if (v !== null && v !== undefined) n.setAttribute(k, String(v));
    for (const kid of kids.flat()) if (kid !== null && kid !== undefined) n.append(kid instanceof Node ? kid : document.createTextNode(String(kid)));
    return n;
  }
  const day = v => v ? new Intl.DateTimeFormat('en-GB', {timeZone: TZ, weekday: 'short', day: 'numeric', month: 'short'}).format(new Date(v)) : '—';
  const dayYear = v => v ? new Intl.DateTimeFormat('en-GB', {timeZone: TZ, day: 'numeric', month: 'short', year: 'numeric'}).format(new Date(v)) : '—';
  const time = v => v ? new Intl.DateTimeFormat('en-GB', {timeZone: TZ, day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit'}).format(new Date(v)) : '—';
  const real = v => v ? new Intl.DateTimeFormat('en-GB', {day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit', second: '2-digit'}).format(new Date(typeof v === 'number' ? v * 1000 : v)) : '—';
  /* Exact minor-unit display from the server's string form (BigInt, no float). */
  function minorText(m) {
    const raw = typeof m === 'object' ? m.minor_str : String(m);
    let v = BigInt(raw), neg = v < 0n; if (neg) v = -v;
    const whole = (v / 100n).toString().replace(/\B(?=(\d{3})+(?!\d))/g, ',');
    return (neg ? '\u2212' : '') + 'CNY ' + whole + '.' + (v % 100n).toString().padStart(2, '0');
  }
  /* Exact "12,345.67" -> minor-unit integer string for policy inputs. */
  function parseMajor(text) {
    const t = String(text).trim().replace(/[\s,]/g, '');
    if (!/^\d{1,13}(\.\d{1,2})?$/.test(t)) throw new Error('Enter an amount like 20000 or 20000.00');
    const [w, f = ''] = t.split('.');
    return Number(BigInt(w) * 100n + BigInt((f + '00').slice(0, 2)));
  }
  let toastTimer = null;
  function toast(message, kind = '') {
    const t = document.getElementById('toast');
    t.replaceChildren(h('div', {class: 'notice ' + kind}, message));
    clearTimeout(toastTimer); toastTimer = setTimeout(() => t.replaceChildren(), kind === 'bad' ? 9000 : 5000);
  }
  class ApiError extends Error { constructor(code, message, status) { super(message); this.code = code; this.status = status; } }
  async function api(path, value, method) {
    const m = method || (value === undefined ? 'GET' : 'POST');
    const r = await fetch(path, {method: m, credentials: 'same-origin', headers: m === 'GET' ? {} : {'Content-Type': 'application/json', 'X-SME-Request': '1'}, body: m === 'GET' ? undefined : JSON.stringify(value || {})});
    let data = null;
    try { data = await r.json(); } catch (_) { throw new ApiError('INVALID_RESPONSE', 'Server returned an unreadable response', r.status); }
    if (!r.ok) {
      const e = data.error || {};
      if (r.status === 401 && window.App) window.App.signedOut();
      throw new ApiError(e.code || 'ERROR', humanError(e.code, e.safe_message), r.status);
    }
    return data.result;
  }
  const ERRORS = {
    APPROVAL_HASH_MISMATCH: 'The command changed since you opened it. Review the refreshed version.',
    STALE_PLAN: 'Facts changed since this plan was built. Recompute the options.',
    STALE_OPTIONS: 'Data changed since the options were computed. Recompute before selecting.',
    INSUFFICIENT_FUNDS: 'Available cash cannot keep the hard reserve after this payment.',
    KILL_SWITCH: 'New sends are stopped. Resume them in Settings first.',
    PRECONDITION_FAILED: 'This action is not due yet, or an earlier step has not settled.',
    POLICY_DENIED: 'Your role does not allow this.',
    OPTION_NOT_EXECUTABLE: 'Only an executable, validated option can be selected.',
    BENEFICIARY_UNVERIFIED: 'The recipient is not verified, so payment is blocked.',
    WORKFLOW_BUSY: 'This Copilot task is still running.',
  };
  const humanError = (code, msg) => (ERRORS[code] || msg || 'Request failed') + (code ? ` (${code})` : '');
  const STATUS = {
    NOT_APPROVED: ['Needs approval', ''], RESERVED: ['Reserved · queued', 'blue'], SUBMITTED: ['Sent · awaiting settlement', 'blue'],
    UNKNOWN: ['Checking status · do not resend', 'warn'], SETTLED: ['Settled & reconciled', 'good'], FAILED: ['Failed · nothing paid', 'bad'],
    EXECUTABLE: ['Executable', 'good'], INFEASIBLE: ['Not feasible', 'bad'], CONDITIONAL: ['Conditional · not executable', 'warn'],
    UNKNOWN_SOLVER: ['Solver did not finish', 'warn'], COMPLETE: ['Complete', 'good'], PAUSED: ['Waiting for you', 'warn'], RUNNING: ['Running', 'blue'],
    FAILED_WF: ['Stopped', 'bad'], CONFIRMED: ['Confirmed by counterparty', 'good'], DECLINED: ['Declined', 'bad'],
  };
  function statusBadge(code, alt) { const [t, c] = STATUS[alt || code] || [code, '']; return h('span', {class: 'badge ' + c}, t); }
  function metric(label, m, note, bad) {
    return h('div', {class: 'card metric' + (bad ? ' bad' : '')}, h('div', {class: 'label'}, label), h('div', {class: 'value num'}, m.display), h('div', {class: 'note'}, note || m.definition || ''));
  }
  function table(headers, rows, opts = {}) {
    const right = new Set(opts.right || []);
    const t = h('table', {}, h('thead', {}, h('tr', {}, headers.map((x, i) => h('th', {class: right.has(i) ? 'r' : '', scope: 'col'}, x)))),
      h('tbody', {}, rows.map(r => h('tr', {}, r.map((c, i) => h('td', {class: right.has(i) ? 'r num' : ''}, c))))));
    const wrap = h('div', {class: 'table-wrap'}, t);
    if (!rows.length) return h('div', {}, wrap, h('p', {class: 'muted small'}, opts.empty || 'Nothing to show.'));
    return wrap;
  }
  const party = s => s;
  /* Step-line cash chart. series: [{name, points:[{at, balance:{minor}}], color, dash}] */
  function chart(series, reserve, opts = {}) {
    const W = 860, H = 280, L = 74, R = 18, T = 18, B = 40;
    const all = series.flatMap(x => x.points);
    if (!all.length) return h('p', {class: 'muted'}, 'No projected movements.');
    const times = all.map(p => +new Date(p.at));
    let t0 = Math.min(...times), t1 = Math.max(...times); if (t1 === t0) t1 = t0 + 86400000;
    t1 += (t1 - t0) * 0.04;
    const vals = all.map(p => p.balance.minor).concat([reserve.minor, 0]);
    let lo = Math.min(...vals), hi = Math.max(...vals); const pad = (hi - lo) * 0.12 || 100000; lo -= pad; hi += pad;
    const x = t => L + (t - t0) / (t1 - t0) * (W - L - R), y = v => T + (hi - v) / (hi - lo) * (H - T - B);
    const svg = s('svg', {viewBox: `0 0 ${W} ${H}`, role: 'img', 'aria-label': opts.label || 'Cash forecast chart'});
    const ticks = 4;
    for (let i = 0; i <= ticks; i++) {
      const v = lo + (hi - lo) * i / ticks, yy = y(v);
      svg.append(s('line', {x1: L, x2: W - R, y1: yy, y2: yy, stroke: '#14141314'}), s('text', {x: L - 8, y: yy + 4, 'text-anchor': 'end', 'font-size': 11, fill: '#5E5D59'}, (Math.round(v / 100000) * 1000).toLocaleString('en-US')));
    }
    svg.append(s('line', {x1: L, x2: W - R, y1: y(0), y2: y(0), stroke: '#14141366', 'stroke-width': 1}));
    svg.append(s('line', {x1: L, x2: W - R, y1: y(reserve.minor), y2: y(reserve.minor), stroke: '#B07A2A', 'stroke-dasharray': '6 4', 'stroke-width': 1.5}));
    svg.append(s('text', {x: W - R, y: y(reserve.minor) - 6, 'text-anchor': 'end', 'font-size': 11, fill: '#7A4A12'}, 'Reserve ' + reserve.display));
    const days = [...new Set(all.map(p => day(p.at)))];
    const seen = new Set();
    for (const p of all.slice().sort((a, b) => new Date(a.at) - new Date(b.at))) {
      const label = day(p.at); if (seen.has(label)) continue; seen.add(label);
      const xx = x(+new Date(p.at));
      svg.append(s('text', {x: xx, y: H - 14, 'text-anchor': 'middle', 'font-size': 11, fill: '#5E5D59'}, label.replace(/^\w+ /, '')));
    }
    void days;
    for (const ser of series) {
      const pts = ser.points.slice().sort((a, b) => new Date(a.at) - new Date(b.at));
      let d = '', prev = null;
      for (const p of pts) {
        const xx = x(+new Date(p.at)), yy = y(p.balance.minor);
        d += prev === null ? `M ${xx} ${yy}` : ` H ${xx} V ${yy}`; prev = yy;
      }
      d += ` H ${W - R}`;
      svg.append(s('path', {d, fill: 'none', stroke: ser.color, 'stroke-width': 2.5, 'stroke-dasharray': ser.dash || null}));
      for (const p of pts) {
        const c = s('circle', {cx: x(+new Date(p.at)), cy: y(p.balance.minor), r: 3.5, fill: '#FAF9F5', stroke: ser.color, 'stroke-width': 2});
        c.append(s('title', {}, `${ser.name} · ${time(p.at)} · ${p.label || ''} · balance ${p.balance.display}`));
        svg.append(c);
      }
    }
    const legend = h('div', {class: 'legend'}, series.map(x => h('span', {}, h('i', {style: {background: x.color}}), x.name)), h('span', {}, h('i', {style: {background: '#B07A2A'}}), 'Hard reserve'));
    const alt = h('details', {}, h('summary', {}, 'Chart as a table'),
      series.map(ser => h('div', {}, h('h4', {class: 'small'}, ser.name), table(['Date', 'Event', 'Balance after'], ser.points.map(p => [time(p.at), p.label || '', p.balance.display]), {right: [2]}))));
    return h('div', {}, h('div', {class: 'chart'}, svg), legend, alt);
  }
  return {h, s, day, dayYear, time, real, minorText, parseMajor, toast, api, ApiError, statusBadge, metric, table, chart, party};
})();
