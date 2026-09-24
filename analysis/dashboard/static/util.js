// Shared helpers: building elements, fetching data, formatting numbers, plain-word labels.

export function h(tag, attrs, ...children) {
  const el = document.createElement(tag);
  setAttrs(el, attrs);
  append(el, children);
  return el;
}

const SVG = 'http://www.w3.org/2000/svg';
export function s(tag, attrs, ...children) {
  const el = document.createElementNS(SVG, tag);
  setAttrs(el, attrs);
  append(el, children);
  return el;
}

function setAttrs(el, attrs) {
  if (!attrs) return;
  for (const [k, v] of Object.entries(attrs)) {
    if (v == null || v === false) continue;
    if (k === 'class') el.setAttribute('class', v);
    else if (k === 'style' && typeof v === 'object') Object.assign(el.style, v);
    else if (k.startsWith('on') && typeof v === 'function') el.addEventListener(k.slice(2), v);
    else if (k === 'text') el.textContent = v;
    else if (v === true) el.setAttribute(k, '');
    else el.setAttribute(k, v);
  }
}

function append(el, children) {
  for (const c of children.flat(Infinity)) {
    if (c == null || c === false || c === '') continue;
    el.append(c instanceof Node ? c : document.createTextNode(String(c)));
  }
}

// Like el.append, but skips null/false/'' (the DOM method would print "null").
export function add(el, ...children) { append(el, children); return el; }

export function clear(el) { while (el.firstChild) el.removeChild(el.firstChild); return el; }

// ---------------------------------------------------------------- data

const cache = new Map();
export async function api(path, { fresh = false } = {}) {
  if (!fresh && cache.has(path)) return cache.get(path);
  const p = fetch('/api/' + path, { headers: { Accept: 'application/json' } }).then(async (r) => {
    let body;
    try { body = await r.json(); } catch { body = { error: `${r.status} ${r.statusText}` }; }
    if (!r.ok) throw new Error(body.error || `${r.status} ${r.statusText}`);
    return body;
  });
  cache.set(path, p);
  p.catch(() => cache.delete(path));
  return p;
}
export function forget(prefix = '') {
  for (const k of [...cache.keys()]) if (k.startsWith(prefix)) cache.delete(k);
}
export const enc = encodeURIComponent;

// ---------------------------------------------------------------- formatting

export const fmt = {
  score(v, d = 3) { return v == null || Number.isNaN(v) ? '–' : Number(v).toFixed(d); },
  pct(v, d) {
    if (v == null || Number.isNaN(v)) return '–';
    if (d == null) d = v > 0 && v < 0.1 ? 1 : 0;
    return (v * 100).toFixed(d) + '%';
  },
  int(v) { return v == null || Number.isNaN(v) ? '–' : Math.round(v).toLocaleString('en-US'); },
  compact(v) {
    if (v == null || Number.isNaN(v)) return '–';
    const a = Math.abs(v);
    if (a >= 1e9) return (v / 1e9).toFixed(a >= 1e10 ? 0 : 1) + 'B';
    if (a >= 1e6) return (v / 1e6).toFixed(a >= 1e7 ? 0 : 1) + 'M';
    if (a >= 1e4) return Math.round(v / 1e3) + 'k';
    if (a >= 1e3) return (v / 1e3).toFixed(1) + 'k';
    return String(Math.round(v));
  },
  dur(seconds) {
    if (seconds == null || Number.isNaN(seconds)) return '–';
    const sgn = seconds < 0 ? '-' : '';
    let s = Math.abs(seconds);
    if (s < 60) return sgn + (s < 10 ? s.toFixed(1) : Math.round(s)) + ' s';
    const m = Math.round(s / 60);
    if (m < 60) return sgn + m + ' min';
    const hh = Math.floor(m / 60), mm = m % 60;
    return sgn + hh + ' h' + (mm ? ' ' + mm + ' min' : '');
  },
  mins(seconds) { return seconds == null ? '–' : (seconds / 60).toFixed(1) + ' min'; },
  hours(seconds) { return seconds == null ? '–' : (seconds / 3600).toFixed(2) + ' h'; },
  when(value) {
    if (value == null) return '–';
    const d = typeof value === 'number' ? new Date(value) : new Date(value);
    if (Number.isNaN(d.getTime())) return String(value);
    const p = (n) => String(n).padStart(2, '0');
    return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}`;
  },
  clock(ms) {
    if (ms == null) return '–';
    const d = new Date(ms), p = (n) => String(n).padStart(2, '0');
    return `${p(d.getHours())}:${p(d.getMinutes())}:${p(d.getSeconds())}`;
  },
  day(value) {
    if (!value) return '–';
    const d = new Date(value), p = (n) => String(n).padStart(2, '0');
    return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`;
  },
  ago(ms) {
    if (ms == null) return '–';
    const s = (Date.now() - ms) / 1000;
    if (s < 5) return 'just now';
    return fmt.dur(s) + ' ago';
  },
  bytes(n) {
    if (n == null) return '–';
    if (n < 1024) return n + ' B';
    if (n < 1024 * 1024) return (n / 1024).toFixed(n < 10240 ? 1 : 0) + ' KB';
    return (n / 1024 / 1024).toFixed(1) + ' MB';
  },
};

export function plural(n, word, many) { return `${fmt.int(n)} ${n === 1 ? word : (many || word + 's')}`; }

// ---------------------------------------------------------------- plain-word labels

export const STATUS = {
  running: 'running now',
  scoring: 'being scored now',
  finished: 'finished',
  interrupted: 'stopped without finishing',
};
export const END = {
  wall_time_budget: 'used its full time',
  max_rounds: 'reached the round limit',
  round_timeout: 'stopped after rounds hit the round time limit',
  context_overflow: 'conversation grew too long for the model',
  pi_process_failure: 'the agent program failed',
  visible_complete_after_review: 'passed every visible test',
  human_abort: 'stopped by hand',
  harness_exception: 'harness error',
};
export const END_SHORT = {
  wall_time_budget: 'full time used',
  max_rounds: 'round limit',
  round_timeout: 'round time limit',
  context_overflow: 'conversation too long',
  pi_process_failure: 'agent program failed',
  visible_complete_after_review: 'passed visible tests',
  human_abort: 'stopped by hand',
  harness_exception: 'harness error',
};
export const STOP = {
  toolUse: 'called a tool',
  stop: 'ended its turn',
  length: 'hit the reply length limit',
  error: 'failed with an error',
  aborted: 'was stopped',
};
export const FAILURE = {
  script_timeout: 'ran out of time',
  candidate_crash: 'program crashed',
  malformed_output: 'output in the wrong shape',
  wrong_results: 'wrong answers',
  no_scored_records: 'nothing to score',
  unexpected_reject: 'rejected a valid program',
  unexpected_accept: 'accepted an invalid program',
  compiler_crash: 'compiler crashed',
  compiler_timeout: 'compiler ran out of time',
  missing_assembly: 'produced no assembly',
  assembly_or_link_failure: 'output did not assemble or link',
  wrong_behavior: 'compiled program gave the wrong result',
  execution_timeout: 'compiled program ran out of time',
  build_failure: 'did not build',
  source_audit_failure: 'failed the source rules check',
};
export const TASK = {
  'c-compiler-ch1-10': 'C compiler (chapters 1–10)',
  'c-compiler-ch1-18': 'C compiler (chapters 1–18)',
  'sql-engine-sqllogictest': 'SQL engine',
};
export const PROFILE = { main: 'main run', pilot: 'trial run' };
export const TIME_KINDS = [
  ['model', 'Model writing', 'var(--c-model)'],
  ['tools', 'Tools running', 'var(--c-tools)'],
  ['summaries', 'Summarizing the conversation', 'var(--c-summaries)'],
  ['startup', 'Starting up / between steps', 'var(--c-startup)'],
  ['lost', 'Lost when the round was cut off', 'var(--c-lost)'],
];
export const CODE_KINDS = [
  ['program code', 'var(--c-model)'],
  ['tests written by the agent', 'var(--c-tools)'],
  ['helper scripts', '#f59e0b'],
  ['scratch files', 'var(--c-startup)'],
  ['notes', 'var(--c-summaries)'],
  ['project settings', '#64748b'],
  ['given to the agent', '#cbd5e1'],
  ['other', '#94a3b8'],
];
export const TOOL_COLORS = {
  bash: '#3b82f6', read: '#10b981', edit: '#f59e0b', write: '#ef4444', grep: '#8b5cf6', find: '#06b6d4',
  ls: '#84cc16', test_visible: '#ec4899', experiment_status: '#64748b', reference_oracle: '#a855f7',
};
const OTHER_TOOL_COLORS = ['#78716c', '#be185d', '#0f766e', '#a16207', '#1e3a8a', '#4d7c0f'];
const otherTools = new Map();
export function toolColor(name) {
  if (TOOL_COLORS[name]) return TOOL_COLORS[name];
  if (!otherTools.has(name)) otherTools.set(name, OTHER_TOOL_COLORS[otherTools.size % OTHER_TOOL_COLORS.length]);
  return otherTools.get(name);
}

// ---------------------------------------------------------------- colors

export const PALETTE = ['#2563eb', '#d97706', '#059669', '#9333ea', '#dc2626', '#0891b2', '#db2777', '#65a30d', '#4b5563', '#7c3aed', '#ea580c', '#0d9488'];
const KNOWN = {
  python: '#2563eb', 'python-typed': '#7c3aed', javascript: '#d97706', typescript: '#0891b2', rust: '#dc2626',
  'js-untyped': '#d97706', 'ts-strict': '#0891b2', baseline: '#4b5563', 'tests-none': '#059669',
  'spec-minimal': '#db2777', 'spec-minimal-tests-none': '#9333ea', 'tests-pushed': '#059669',
};
export function variantColors(variants) {
  const out = {};
  const used = new Set();
  for (const v of variants) if (KNOWN[v] && !used.has(KNOWN[v])) { out[v] = KNOWN[v]; used.add(KNOWN[v]); }
  let i = 0;
  for (const v of variants) {
    if (out[v]) continue;
    while (used.has(PALETTE[i % PALETTE.length]) && i < PALETTE.length * 2) i++;
    out[v] = PALETTE[i % PALETTE.length];
    used.add(out[v]);
    i++;
  }
  return out;
}

export function isDark() {
  const t = document.documentElement.dataset.theme;
  if (t) return t === 'dark';
  return window.matchMedia('(prefers-color-scheme: dark)').matches;
}

// 0 = red, 1 = green; readable in both themes.
export function heatColor(v) {
  if (v == null || Number.isNaN(v)) return 'transparent';
  const hue = Math.max(0, Math.min(1, v)) * 125;
  return isDark() ? `hsl(${hue} 45% ${22 + v * 6}%)` : `hsl(${hue} 70% ${86 - v * 6}%)`;
}

// ---------------------------------------------------------------- tooltip

const tipEl = () => document.getElementById('tip');
export function showTip(event, content) {
  const tip = tipEl();
  clear(tip);
  if (content instanceof Node) tip.append(content); else tip.textContent = content;
  tip.hidden = false;
  const pad = 14;
  const { innerWidth: W, innerHeight: H } = window;
  const r = tip.getBoundingClientRect();
  let x = event.clientX + pad, y = event.clientY + pad;
  if (x + r.width > W - 8) x = event.clientX - r.width - pad;
  if (y + r.height > H - 8) y = event.clientY - r.height - pad;
  tip.style.left = Math.max(4, x) + 'px';
  tip.style.top = Math.max(4, y) + 'px';
}
export function hideTip() { const t = tipEl(); if (t) t.hidden = true; }
export function tipLines(title, lines) {
  return h('div', null, title ? h('b', null, title) : null, ...lines.filter(Boolean).map((l) => h('div', null, l)));
}

// ---------------------------------------------------------------- components

export function kpi(label, value, note, cls) {
  return h('div', { class: 'kpi' }, h('div', { class: 'label' }, label),
    h('div', { class: 'value ' + (cls || '') }, value), note ? h('div', { class: 'note' }, note) : null);
}

export function card(title, explain, ...body) {
  return h('section', { class: 'card' }, title ? h('h3', null, title) : null,
    explain ? h('p', { class: 'explain' }, explain) : null, ...body);
}

export function cardHead(title, controls, explain) {
  return [h('div', { class: 'card-head' }, h('h3', null, title), h('span', { class: 'spacer' }), controls || null),
    explain ? h('p', { class: 'explain' }, explain) : null];
}

export function segmented(options, value, onChange) {
  const wrap = h('div', { class: 'seg' });
  for (const [key, label] of options) {
    const b = h('button', { class: key === value ? 'on' : '', type: 'button' }, label);
    b.addEventListener('click', () => {
      for (const x of wrap.children) x.classList.remove('on');
      b.classList.add('on');
      onChange(key);
    });
    wrap.append(b);
  }
  return wrap;
}

export function pill(text, cls) { return h('span', { class: 'pill ' + (cls || '') }, text); }

export function scoreBar(v, color) {
  const w = v == null ? 0 : Math.max(0, Math.min(1, v)) * 100;
  return h('span', { class: 'bar', title: fmt.score(v) },
    h('span', { style: { width: w + '%', background: color || heatColorSolid(v) } }));
}
export function heatColorSolid(v) {
  if (v == null) return 'var(--grid)';
  const hue = Math.max(0, Math.min(1, v)) * 125;
  return `hsl(${hue} 65% 45%)`;
}

// A sortable table. columns: [{key, label, num, sort(row), render(row), title, cls}]
export function table(columns, rows, { onRow, sortKey, sortDir = -1, rowClass, empty = 'Nothing to show.', maxHeight } = {}) {
  const wrap = h('div', { class: 'tablewrap', style: maxHeight ? { maxHeight, overflowY: 'auto' } : null });
  let key = sortKey, dir = sortDir;
  const draw = () => {
    clear(wrap);
    const sorted = rows.slice();
    const col = columns.find((c) => c.key === key);
    if (col) {
      const get = col.sort || ((r) => r[col.key]);
      sorted.sort((a, b) => {
        const x = get(a), y = get(b);
        if (x == null && y == null) return 0;
        if (x == null) return 1;
        if (y == null) return -1;
        return (x < y ? -1 : x > y ? 1 : 0) * dir;
      });
    }
    const thead = h('thead', null, h('tr', null, columns.map((c) => {
      const th = h('th', { class: (c.num ? 'num ' : '') + (c.nosort ? '' : 'sortable'), title: c.title || null },
        c.label, c.key === key ? h('span', { class: 'arrow' }, dir > 0 ? '▲' : '▼') : null);
      if (!c.nosort) th.addEventListener('click', () => { if (key === c.key) dir = -dir; else { key = c.key; dir = c.num ? -1 : 1; } draw(); });
      return th;
    })));
    const tbody = h('tbody');
    if (!sorted.length) tbody.append(h('tr', null, h('td', { colspan: columns.length, class: 'muted' }, empty)));
    for (const r of sorted) {
      const tr = h('tr', { class: (onRow ? 'clickable ' : '') + (rowClass ? rowClass(r) || '' : '') },
        columns.map((c) => h('td', { class: (c.num ? 'num ' : '') + (c.cls || '') }, c.render ? c.render(r) : (r[c.key] ?? '–'))));
      if (onRow) tr.addEventListener('click', (e) => { if (e.target.closest('a,button,input,summary')) return; onRow(r, e); });
      tbody.append(tr);
    }
    wrap.append(h('table', { class: 'data' }, thead, tbody));
  };
  draw();
  return wrap;
}

export function runName(r) {
  const variant = r.variant || '(variant not recorded)';
  if (r.profile === 'pilot') return `${variant} · trial${r.repeat ? ' ' + r.repeat : ''}`;
  return r.repeat ? `${variant} · run ${r.repeat}` : variant;
}

export function statusPill(r) {
  const label = STATUS[r.status] || r.status || 'unknown';
  return pill(label, r.status);
}

export function lazyDetails(summaryText, build, { open = false, cls } = {}) {
  const d = h('details', { class: cls || null });
  d.append(h('summary', null, summaryText));
  let built = false;
  const fill = () => { if (!built && d.open) { built = true; d.append(build()); } };
  d.addEventListener('toggle', fill);
  if (open) { d.open = true; fill(); }
  return d;
}

export function median(values) {
  const v = values.filter((x) => x != null && !Number.isNaN(x)).sort((a, b) => a - b);
  if (!v.length) return null;
  const m = Math.floor(v.length / 2);
  return v.length % 2 ? v[m] : (v[m - 1] + v[m]) / 2;
}

export function sum(values) { return values.reduce((a, b) => a + (b || 0), 0); }

export function errorBox(error) {
  return h('div', { class: 'error' }, 'Could not load this: ' + (error && error.message ? error.message : String(error)));
}

export function scoreCell(v, frozen) {
  if (frozen == null) return fmt.score(v);
  return h('span', { title: `corrected score; the value recorded at the time was ${fmt.score(frozen)}` }, fmt.score(v), h('span', { class: 'warn' }, ' *'));
}

export function activityText(a) {
  if (!a || !a.doing) return 'No activity recorded yet.';
  let t = `Now: ${a.doing}`;
  if (a.doing === 'writing a reply' && a.detail) {
    t += ` (${fmt.int(a.detail.thinking_chars)} characters of thinking, ${fmt.int(a.detail.text_chars + a.detail.tool_call_chars)} of answer so far)`;
  } else if (a.doing === 'running a tool' && a.detail) {
    t += `: ${a.detail.name} ${String(a.detail.what || '').slice(0, 120)}`;
  }
  if (a.last_saved) t += ` · last saved step ${fmt.ago(a.last_saved)}`;
  return t;
}
