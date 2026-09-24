// Router and the top-level pages: batches, one batch, compare, reports, model server.

import {
  h, clear, api, forget, fmt, enc, END, TASK, STATUS, PROFILE, TIME_KINDS, CODE_KINDS, variantColors, card, cardHead,
  segmented, table, runName, statusPill, pill, kpi, median, sum, errorBox, heatColor, showTip, hideTip, toolColor,
  tipLines, plural, FAILURE, scoreCell, activityText, END_SHORT,
} from './util.js';
import { lineChart, barChart, dotPlot, heatmap, dotStrip, scoreAxis } from './charts.js';
import { runPage } from './run.js';
import { renderMarkdown } from './markdown.js';

const main = document.getElementById('app');
let leaving = [];
export function onLeave(fn) { leaving.push(fn); }

// ---------------------------------------------------------------- routing

function parseHash() {
  const raw = location.hash.replace(/^#/, '') || '/';
  const [path, qs] = raw.split('?');
  return { path, params: new URLSearchParams(qs || '') };
}

export function go(path, params) {
  const q = params ? '?' + new URLSearchParams(params).toString() : '';
  location.hash = '#' + path + q;
}

let token = 0;
async function render() {
  for (const fn of leaving) { try { fn(); } catch { /* ignore */ } }
  leaving = [];
  hideTip();
  const my = ++token;
  const { path, params } = parseHash();
  const segs = path.split('/').filter(Boolean).map(decodeURIComponent);
  for (const a of document.querySelectorAll('[data-nav]')) {
    const nav = a.dataset.nav;
    a.classList.toggle('on', (nav === 'home' && (!segs.length || segs[0] === 'batch' || segs[0] === 'run'))
      || nav === segs[0] || (nav === 'docs' && segs[0] === 'doc'));
  }
  clear(main);
  main.append(h('p', { class: 'loading' }, 'Loading…'));
  const stale = () => my !== token;
  try {
    const view = h('div');
    if (!segs.length) await home(view, stale);
    else if (segs[0] === 'batch') await batchPage(view, segs[1], params, stale);
    else if (segs[0] === 'run') await runPage(view, segs[1], segs[2] || 'overview', params, stale, { onLeave, go });
    else if (segs[0] === 'compare') await comparePage(view, params, stale);
    else if (segs[0] === 'docs') await docsPage(view);
    else if (segs[0] === 'doc') await docPage(view, segs.slice(1).join('/'), params);
    else if (segs[0] === 'server') await serverPage(view);
    else view.append(h('p', null, 'Nothing here. ', h('a', { href: '#/' }, 'Back to the batches.')));
    if (stale()) return;
    clear(main);
    main.append(view);
    if (view.afterMount) view.afterMount();
  } catch (error) {
    if (stale()) return;
    clear(main);
    main.append(errorBox(error));
    console.error(error);
  }
}

window.addEventListener('hashchange', render);

// theme, refresh, find-a-run box
(function chrome() {
  const root = document.documentElement;
  try { const saved = localStorage.getItem('picc-theme'); if (saved) root.dataset.theme = saved; } catch { /* private mode */ }
  document.getElementById('theme').addEventListener('click', () => {
    const dark = root.dataset.theme ? root.dataset.theme === 'dark' : window.matchMedia('(prefers-color-scheme: dark)').matches;
    root.dataset.theme = dark ? 'light' : 'dark';
    try { localStorage.setItem('picc-theme', root.dataset.theme); } catch { /* ignore */ }
    render();
  });
  document.getElementById('refresh').addEventListener('click', () => { forget(); render(); });
  const find = document.getElementById('find');
  const list = document.getElementById('find-list');
  let ids = [];
  api('runs').then((runs) => {
    ids = runs.map((r) => r.id);
    const batches = [...new Set(runs.map((r) => r.batch))];
    for (const b of batches) list.append(h('option', { value: b }, 'batch'));
    for (const r of runs) list.append(h('option', { value: r.id }, `${r.variant || ''} ${r.final != null ? fmt.score(r.final) : ''}`));
  }).catch(() => {});
  const jump = () => {
    const v = find.value.trim();
    if (!v) return;
    if (ids.includes(v)) go('/run/' + enc(v));
    else if (/^(v\d+|probes|early)$/.test(v)) go('/batch/' + v);
    else {
      const hit = ids.find((id) => id.includes(v));
      if (hit) go('/run/' + enc(hit));
    }
    find.value = '';
    find.blur();
  };
  find.addEventListener('change', jump);
  find.addEventListener('keydown', (e) => { if (e.key === 'Enter') jump(); });
})();

// ---------------------------------------------------------------- home: every batch

async function home(view, stale) {
  const data = await api('overview', { fresh: true });
  view.append(h('h1', null, 'Experiment results'));
  view.append(h('p', { class: 'sub' }, `${plural(data.runs, 'run')} in ${plural(data.batches.length, 'batch', 'batches')}. `,
    'Scores are the final score on the hidden tests (0 to 1) unless a page says otherwise; corrected re-scores are used where a batch has them.'));
  const srv = data.server || {};
  view.append(h('p', { class: 'small muted' }, 'Model server: ',
    srv.running ? h('span', { class: 'good' }, `running (process ${srv.pid})`) : h('span', { class: 'warn' }, 'not running'),
    srv.launch ? ` · configuration launched ${srv.launch}` : '', ' · ', h('a', { href: '#/server' }, 'details'),
    ' · Thinking tokens: ', data.tokenizer));
  if (data.warm && data.warm.running) {
    view.append(h('div', { class: 'notice' },
      `Reading run records for the first time: ${data.warm.done} of ${data.warm.total} runs done. Numbers fill in as this finishes; this page refreshes itself.`));
    const t = setTimeout(() => { if (!stale()) { forget('overview'); render(); } }, 4000);
    onLeave(() => clearTimeout(t));
  }
  if (data.live.length) {
    view.append(h('h2', null, 'Running now'));
    const grid = h('div', { class: 'batches' });
    for (const r of data.live) grid.append(liveCard(r));
    view.append(grid);
    const t = setInterval(() => { if (!stale()) { forget('overview'); render(); } }, 20000);
    onLeave(() => clearInterval(t));
  }
  view.append(h('h2', null, 'Batches'));
  const grid = h('div', { class: 'batches' });
  for (const b of data.batches) grid.append(batchCard(b));
  view.append(grid);
}

function liveCard(r) {
  const used = r.elapsed_s || 0;
  const budget = (r.budget_hours || 0) * 3600;
  const c = h('section', { class: 'card batch-card live-card' },
    h('div', { class: 'top' }, h('span', { class: 'key' }, h('a', { href: `#/run/${enc(r.id)}` }, r.id)), statusPill(r)),
    h('div', { class: 'facts' }, `${TASK[r.task] || r.task} · ${runName(r)} · round ${r.state_round ?? r.rounds} of ${r.max_rounds ?? '?'}`),
    budget ? h('div', { class: 'progress', title: `${fmt.dur(used)} of ${fmt.dur(budget)}` }, h('span', { style: { width: Math.min(100, (used / budget) * 100) + '%' } })) : null,
    h('div', { class: 'facts' }, `time used ${fmt.dur(used)}${budget ? ' of ' + fmt.dur(budget) : ''} · progress score ${fmt.score(r.visible_final)}`),
    h('div', { class: 'facts activity' }, 'Checking what it is doing…'));
  api(`run/${enc(r.id)}/activity`, { fresh: true }).then((a) => {
    const el = c.querySelector('.activity');
    el.textContent = activityText(a);
  }).catch(() => {});
  return c;
}

function batchCard(b) {
  const mainOnly = b.main >= 3;
  const shown = b.dots.filter((d) => !mainOnly || d[4] === 'main');
  const variants = [...new Set(shown.map((d) => d[0]))];
  const colors = variantColors(variants.length ? variants : b.variants);
  const groups = variants.map((v) => ({
    name: v, color: colors[v],
    points: shown.filter((d) => d[0] === v).map((d) => ({
      y: d[2], id: d[3], hollow: d[5] !== 'finished' || d[4] !== 'main',
      label: `${d[3]}\nfinal score ${fmt.score(d[2])}${d[4] !== 'main' ? '\ntrial run' : ''}${d[5] !== 'finished' ? '\n(' + (STATUS[d[5]] || d[5]) + ')' : ''}`,
    })),
  }));
  const tasks = b.tasks.map((t) => TASK[t] || t).join(' + ');
  const docs = b.docs || {};
  return h('section', { class: 'card batch-card' },
    h('div', { class: 'top' },
      h('span', { class: 'key' }, h('a', { href: `#/batch/${b.key}` }, b.key === 'early' || b.key === 'probes' ? b.title : b.key)),
      h('span', { class: 'title' }, b.key === 'early' || b.key === 'probes' ? b.subtitle : (b.subtitle || '')),
      b.running ? pill(`${b.running} running`, 'running') : null),
    h('div', { class: 'facts' }, `${tasks} · ${plural(b.main, 'main run')}${b.pilot ? ` + ${plural(b.pilot, 'trial run')}` : ''}`,
      b.interrupted ? ` · ${b.interrupted} stopped early` : '', ` · ${fmt.day(b.first_start)}${b.last_end && fmt.day(b.last_end) !== fmt.day(b.first_start) ? ' → ' + fmt.day(b.last_end) : ''}`,
      b.server.length ? ` · ${b.server.join(', ')}` : ''),
    groups.length ? dotStrip({ groups, onClick: (p) => go('/run/' + enc(p.id)) }) : null,
    h('div', { class: 'row small' },
      h('span', { class: 'muted' }, variants.map((v) => h('span', { class: 'nowrap', style: { marginRight: '10px' } }, h('span', { class: 'dot', style: { background: colors[v] } }), v || '(not recorded)'))),
      h('span', { class: 'spacer' }),
      b.best ? h('span', { class: 'muted nowrap' }, 'best ', h('a', { href: `#/run/${enc(b.best.id)}` }, fmt.score(b.best.score))) : null),
    h('div', { class: 'links small' },
      h('a', { href: `#/batch/${b.key}` }, 'Open batch →'),
      docs.plan ? h('a', { href: `#/doc/${docs.plan}` }, 'Plan') : null,
      docs.results ? h('a', { href: `#/doc/${docs.results}` }, 'Results') : null,
      ...(docs.reports || []).map((r) => h('a', { href: `#/doc/${r}` }, 'Report ' + r.replace(/^.*REPORT_|\.md$/g, '')))));
}

// ---------------------------------------------------------------- one batch

async function batchPage(view, key, params, stale) {
  const data = await api(`batch/${enc(key)}`, { fresh: true });
  const runs = data.runs;
  const docs = data.docs;
  view.append(h('div', { class: 'crumbs' }, h('a', { href: '#/' }, 'Batches'), ' › ', key));
  view.append(h('h1', null, key === 'early' || key === 'probes' ? docs.title : `${key}${docs.subtitle ? ' — ' + docs.subtitle : ''}`));
  const all = Object.values(runs);
  const starts = all.map((r) => r.started_at).filter(Boolean).sort();
  const ends = all.map((r) => r.ended_at).filter(Boolean).sort();
  view.append(h('p', { class: 'sub' },
    `${plural(all.length, 'run')} · ${fmt.when(starts[0])} → ${fmt.when(ends[ends.length - 1])} · model ${[...new Set(all.map((r) => r.model))].join(', ')}`));
  view.append(h('div', { class: 'links' },
    docs.plan ? h('a', { href: `#/doc/${docs.plan}` }, 'Experiment plan') : null,
    docs.results ? h('a', { href: `#/doc/${docs.results}` }, 'Results write-up') : null,
    ...(docs.reports || []).map((r) => h('a', { href: `#/doc/${r}` }, 'Report ' + r.replace(/^.*REPORT_|\.md$/g, ''))),
    h('a', { href: `#/compare?runs=${all.filter((r) => r.profile === 'main').map((r) => enc(r.id)).join(',')}` }, 'Compare these runs')));
  for (const st of data.studies) {
    if (stale()) return;
    view.append(studySection(st, runs, data.studies.length > 1));
  }
}

function studySection(st, runs, several) {
  const sec = h('div');
  const rows = st.runs.map((id) => runs[id]);
  const counted = rows.filter((r) => r.profile === 'main' && r.status === 'finished' && r.comparable);
  const other = rows.filter((r) => !counted.includes(r));
  const variants = st.variants.map((v) => v.id);
  const colors = variantColors(variants);
  const main = counted.length ? counted : rows;
  if (several || st.id) {
    sec.append(h('h2', null, `${TASK[st.task] || st.task}`, h('span', { class: 'muted small', style: { fontWeight: 400, marginLeft: '10px' } }, st.id)));
  }
  const reasoningReady = main.every((r) => r.reasoning && r.reasoning.status === 'ready');

  // scores by variant
  const metrics = [
    ['final', 'Final score', (r) => r.scores.final],
    ['visible', 'Progress score', (r) => r.scores.visible_final],
    ['best', 'Best final score during the run', (r) => r.scores.best],
    ['built', 'Last version that built', (r) => r.scores.last_built],
  ];
  if (main.some((r) => r.scores.fuzz)) metrics.push(['fuzz', 'Random-program check', (r) => r.scores.fuzz && r.scores.fuzz.final]);
  let metric = 'final';
  const plotBox = h('div');
  const drawPlot = () => {
    clear(plotBox);
    const get = metrics.find((m) => m[0] === metric)[2];
    plotBox.append(dotPlot({
      groups: st.variants.map((v) => ({
        name: v.id, color: colors[v.id],
        points: main.filter((r) => r.variant === v.id).map((r) => ({ y: get(r), id: r.id, tag: r.repeat ? 'r' + r.repeat : '', label: runName(r), hollow: r.status !== 'finished' })),
      })).filter((g) => g.points.length),
      y: { min: 0, max: 1, label: 'score' },
      tooltip: (p) => tipLines(p.id, [`${metrics.find((m) => m[0] === metric)[1]}: ${fmt.score(p.y)}`, 'click to open the run']),
      onClick: (p) => go('/run/' + enc(p.id)),
    }));
  };
  drawPlot();
  const variantNotes = h('div', { class: 'small', style: { marginTop: '6px' } }, st.variants.map((v) =>
    h('div', null, h('span', { class: 'dot', style: { background: colors[v.id] } }), h('b', null, v.id), v.description ? h('span', { class: 'muted' }, ' — ' + v.description) : null)));
  const scoreCard = h('section', { class: 'card' },
    ...cardHead('Scores by variant', segmented(metrics.map((m) => [m[0], m[1].replace(' during the run', '')]), metric, (k) => { metric = k; drawPlot(); }),
      'Each dot is one run; the faint bar is the middle run of each variant. Final score = share of the hidden tests passed by the last saved version (0 to 1). Hollow dots are runs that did not finish normally.'),
    plotBox, variantNotes);

  // progress over time
  const series = [];
  for (const r of main) {
    const pts = (r.scores.visible || []).filter((v) => v.score != null).map((v) => ({ x: v.t, y: v.score, round: v.round, built: v.built, hollow: v.built === false }));
    if (pts.length) series.push({ name: runName(r), color: colors[r.variant], points: [{ x: 0, y: 0, round: -1 }, ...pts], run: r });
  }
  const progress = lineChart({
    series, height: 280, y: scoreAxis('progress score'), x: { time: true, min: 0, label: 'time since the run started' }, dots: true,
    tooltip: (p, sr) => tipLines(sr.name, [p.round < 0 ? 'start' : `after round ${p.round}: ${fmt.score(p.y)}`, p.built === false ? 'did not build' : null, `at ${fmt.dur(p.x)}`]),
    onClick: (p, sr) => go('/run/' + enc(sr.run.id)),
  });

  // table
  const cols = [
    { key: 'id', label: 'Run', render: (r) => h('a', { href: `#/run/${enc(r.id)}` }, runName(r)), sort: (r) => `${variants.indexOf(r.variant)}-${String(r.repeat).padStart(3, '0')}` },
    { key: 'final', label: 'Final', num: true, title: 'final score on the hidden tests', render: (r) => scoreCell(r.scores.final, r.scores.final_frozen), sort: (r) => r.scores.final },
    { key: 'visible', label: 'Progress', num: true, title: 'score on the visible tests after the last round', render: (r) => fmt.score(r.scores.visible_final), sort: (r) => r.scores.visible_final },
    { key: 'rounds', label: 'Rounds', num: true },
    { key: 'elapsed_s', label: 'Time', num: true, render: (r) => fmt.dur(r.elapsed_s) },
    { key: 'replies', label: 'Replies', num: true, render: (r) => fmt.int(r.totals?.replies), sort: (r) => r.totals?.replies },
    { key: 'out', label: 'Tokens written', num: true, render: (r) => fmt.compact(r.totals?.out), sort: (r) => r.totals?.out, title: 'everything the model wrote, thinking included' },
    { key: 'think', label: 'Thinking', num: true, render: (r) => (r.reasoning?.total != null && r.totals?.out ? fmt.pct(r.reasoning.total / r.totals.out) : '–'), sort: (r) => (r.reasoning?.total != null ? r.reasoning.total / r.totals.out : null), title: 'share of written tokens that were thinking' },
    { key: 'in', label: 'Tokens read', num: true, render: (r) => fmt.compact(r.totals?.in), sort: (r) => r.totals?.in, title: 'conversation the model read, summed over replies' },
    { key: 'calls', label: 'Tool calls', num: true, render: (r) => fmt.int(r.totals?.calls), sort: (r) => r.totals?.calls },
    { key: 'failed', label: 'Failed', num: true, render: (r) => fmt.int(r.totals?.failed), sort: (r) => r.totals?.failed },
    { key: 'blocked', label: 'Blocked', num: true, render: (r) => fmt.int(r.totals?.blocked), sort: (r) => r.totals?.blocked, title: 'commands the rule checker refused' },
    { key: 'summaries', label: 'Summaries', num: true, render: (r) => fmt.int(r.totals?.summaries), sort: (r) => r.totals?.summaries, title: 'times the conversation was summarized to make room' },
    { key: 'code', label: 'Code lines', num: true, render: (r) => fmt.int(r.code?.final?.['program code']?.lines), sort: (r) => r.code?.final?.['program code']?.lines },
    { key: 'tests', label: 'Test lines', num: true, render: (r) => fmt.int(r.code?.final?.['tests written by the agent']?.lines ?? 0), sort: (r) => r.code?.final?.['tests written by the agent']?.lines ?? 0, title: 'lines of tests the agent wrote for itself' },
    { key: 'end', label: 'Ended', render: (r) => h('span', { class: 'small nowrap', title: r.status === 'finished' ? (END[r.end_reason] || '') : '' }, r.status === 'finished' ? (END_SHORT[r.end_reason] || r.end_reason || '') : STATUS[r.status] || r.status), sort: (r) => r.end_reason },
  ];
  const tbl = table(cols, main, { sortKey: 'id', sortDir: 1, onRow: (r) => go('/run/' + enc(r.id)) });

  // per-test heat map
  const withTests = main.filter((r) => r.final_tests);
  let heat = null;
  if (withTests.length) {
    const colsT = withTests[0].final_tests.columns;
    const ordered = withTests.slice().sort((a, b) => variants.indexOf(a.variant) - variants.indexOf(b.variant) || (a.repeat || 0) - (b.repeat || 0));
    const kind = withTests[0].final_tests.kind;
    heat = h('section', { class: 'card' },
      ...cardHead(kind === 'test' ? 'Score on each hidden test' : 'Score on each stage of the hidden tests', null,
        kind === 'test' ? 'Each column is one hidden test script; the number is the share of its checks the final version passed. Hover for what went wrong.'
          : 'Each column is one chapter stage; the number is the stage score of the final version.'),
      heatmap({
        rows: ordered.map((r) => ({ label: runName(r), onClick: () => go(`/run/${enc(r.id)}/tests`) })),
        cols: colsT.map((c) => c.replace(/^evidence\//, '').replace(/\.test$/, '')),
        colTitles: colsT,
        cells: ordered.map((r) => colsT.map((c) => { const i = r.final_tests.columns.indexOf(c); return i < 0 ? null : r.final_tests.scores[i]; })),
        title: (i, j, v) => { const r = ordered[i]; const k = r.final_tests.columns.indexOf(colsT[j]); const f = k >= 0 ? r.final_tests.failures[k] : null; return `${runName(r)}\n${colsT[j]}: ${fmt.score(v)}${f ? '\n' + (FAIL_LABEL(f)) : ''}`; },
      }));
  }

  // where the time went, tokens, tool use, code size
  const order = main.slice().sort((a, b) => variants.indexOf(a.variant) - variants.indexOf(b.variant) || (a.repeat || 0) - (b.repeat || 0));
  const cats = order.map((r) => ({ label: runName(r), title: r.id }));
  const open = (i) => go('/run/' + enc(order[i].id));
  const timeChart = barChart({
    categories: cats, format: (v) => fmt.dur(v), time: true, catLabel: open, onClick: open,
    series: TIME_KINDS.map(([k, label, color]) => ({ name: label, color, values: order.map((r) => r.totals?.time?.[k] || 0) })),
    tooltip: (i, j) => { const r = order[i]; const t = r.totals.time; const all = sum(Object.values(t)); return tipLines(runName(r), TIME_KINDS.map(([k, label]) => `${label}: ${fmt.dur(t[k])} (${fmt.pct(t[k] / all)})`)); },
  });
  const tokenChart = barChart({
    categories: cats, catLabel: open, onClick: open,
    series: reasoningReady ? [
      { name: 'thinking', color: 'var(--c-thinking)', values: order.map((r) => r.reasoning.total) },
      { name: 'answers and tool calls', color: 'var(--c-answer)', values: order.map((r) => (r.totals?.out || 0) - r.reasoning.total) },
    ] : [{ name: 'tokens written', color: 'var(--c-answer)', values: order.map((r) => r.totals?.out || 0) }],
    tooltip: (i) => { const r = order[i]; return tipLines(runName(r), [`written: ${fmt.int(r.totals?.out)} tokens`, r.reasoning?.total != null ? `thinking: ${fmt.int(r.reasoning.total)} (${fmt.pct(r.reasoning.total / r.totals.out)})` : 'thinking: not counted', `per reply (middle): ${fmt.int(r.totals?.out_median)}`, `speed: ${fmt.int(r.totals?.tokens_per_min)} tokens per minute of writing`]); },
  });
  const readChart = barChart({
    categories: cats, catLabel: open, onClick: open,
    series: [
      { name: 're-used from the server’s memory', color: 'var(--c-cached)', values: order.map((r) => r.totals?.cached || 0) },
      { name: 'read fresh', color: 'var(--c-fresh)', values: order.map((r) => (r.totals?.in || 0) - (r.totals?.cached || 0)) },
    ],
    tooltip: (i) => { const r = order[i]; return tipLines(runName(r), [`read: ${fmt.int(r.totals?.in)} tokens over ${fmt.int(r.totals?.replies)} replies`, `re-used: ${fmt.pct((r.totals?.cached || 0) / (r.totals?.in || 1), 1)}`, `largest conversation: ${fmt.int(r.totals?.conv_max)} tokens`]); },
  });
  const tools = [...new Set(order.flatMap((r) => Object.keys(r.totals?.by_tool || {})))];
  tools.sort((a, b) => sum(order.map((r) => r.totals?.by_tool?.[b]?.calls || 0)) - sum(order.map((r) => r.totals?.by_tool?.[a]?.calls || 0)));
  const toolChart = barChart({
    categories: cats, format: fmt.int, catLabel: open, onClick: open,
    series: tools.map((t, i) => ({ name: t, color: toolColor(t, i), values: order.map((r) => r.totals?.by_tool?.[t]?.calls || 0) })),
    tooltip: (i, j) => { const r = order[i]; const bt = r.totals.by_tool; return tipLines(runName(r), [...tools.filter((t) => bt[t]).map((t) => `${t}: ${fmt.int(bt[t].calls)} calls, ${fmt.int(bt[t].failed)} failed, ${fmt.dur(bt[t].seconds)}`)]); },
  });
  const codeChart = barChart({
    categories: cats, format: fmt.int, catLabel: open, onClick: open,
    series: CODE_KINDS.slice(0, 5).map(([k, color]) => ({ name: k, color, values: order.map((r) => r.code?.final?.[k]?.lines || 0) })),
    tooltip: (i) => { const r = order[i]; const f = r.code?.final || {}; return tipLines(runName(r), Object.entries(f).map(([k, v]) => `${k}: ${fmt.int(v.lines)} lines in ${plural(v.files, 'file')}`)); },
  });

  sec.append(h('div', { class: 'grid2' }, scoreCard,
    h('section', { class: 'card' }, ...cardHead('Progress over time', null, 'Score on the visible tests after each round, against time since the run started. Hollow points did not build. Click a line to open that run; click a name in the legend to hide it.'), progress)));
  sec.append(h('section', { class: 'card' }, ...cardHead('Runs', null, `Click a row to open the run. ${counted.length ? 'Only finished main runs are listed here; the rest are below.' : ''}`), tbl));
  if (heat) sec.append(heat);
  sec.append(h('div', { class: 'grid2' },
    h('section', { class: 'card' }, ...cardHead('Where the time went', null, 'Wall-clock time of each run, split by what was happening, measured from the saved conversation.'), timeChart),
    h('section', { class: 'card' }, ...cardHead('Tokens written by the model', null, reasoningReady ? 'Thinking is counted with the model’s own tokenizer from the streamed text.' : `Thinking share not shown: ${runsNote(main)}.`), tokenChart)));
  sec.append(h('div', { class: 'grid2' },
    h('section', { class: 'card' }, ...cardHead('Tokens read by the model', null, 'Every reply re-reads the whole conversation; most of it is served from the server’s memory of the previous request.'), readChart),
    h('section', { class: 'card' }, ...cardHead('Tool calls', null, 'Calls by tool. Hover for failures and time spent.'), toolChart)));
  sec.append(h('section', { class: 'card' }, ...cardHead('What the agent left behind (final version)', null, 'Lines in the final saved version, by kind of file. “Program code” is what the build uses; tests are files the agent wrote to check itself.'), codeChart));
  if (other.length && counted.length) {
    sec.append(h('h3', null, 'Other runs in this batch'));
    sec.append(h('p', { class: 'explain' }, 'Trial runs, runs that were resumed after an interruption, and runs that did not finish. They are not part of the comparison above.'));
    sec.append(table([
      cols[0], cols[1], cols[2], cols[3], cols[4],
      { key: 'profile', label: 'Kind', render: (r) => PROFILE[r.profile] || r.profile },
      { key: 'status', label: 'Status', render: (r) => h('span', null, statusPill(r), r.resumed ? ' resumed' : '', r.status === 'finished' ? ' · ' + (END[r.end_reason] || r.end_reason || '') : '') },
    ], other, { sortKey: 'id', sortDir: 1, onRow: (r) => go('/run/' + enc(r.id)) }));
  }
  return sec;
}

function runsNote(rows) {
  const st = rows.map((r) => r.reasoning?.status);
  if (st.includes('unavailable')) return 'the model’s tokenizer is not available to this dashboard';
  if (st.includes('counting')) return 'still being counted — reload in a minute';
  return 'not counted yet — open a run to count it';
}

function FAIL_LABEL(k) { return FAILURE[k] || k; }


// ---------------------------------------------------------------- compare

async function comparePage(view, params, stale) {
  const ids = (params.get('runs') || '').split(',').map(decodeURIComponent).filter(Boolean);
  view.append(h('h1', null, 'Compare runs'));
  const index = await api('runs');
  const byId = Object.fromEntries(index.map((r) => [r.id, r]));
  const chosen = ids.filter((id) => byId[id]);
  const picker = h('div', { class: 'card' });
  const input = h('input', { class: 'pick', list: 'cmp-list', placeholder: 'Type a run name…', style: { width: '280px' } });
  const dl = h('datalist', { id: 'cmp-list' }, index.map((r) => h('option', { value: r.id }, `${r.variant} ${fmt.score(r.final)}`)));
  const setRuns = (list) => go('/compare', list.length ? { runs: list.join(',') } : null);
  const add = () => { const v = input.value.trim(); if (byId[v] && !chosen.includes(v)) setRuns([...chosen, v]); };
  input.addEventListener('change', add);
  const batches = [...new Set(index.map((r) => r.batch))];
  const batchSel = h('select', { class: 'pick' }, h('option', { value: '' }, 'Add all main runs of a batch…'), batches.map((b) => h('option', { value: b }, b)));
  batchSel.addEventListener('change', () => {
    const add2 = index.filter((r) => r.batch === batchSel.value && r.profile === 'main').map((r) => r.id);
    setRuns([...new Set([...chosen, ...add2])]);
  });
  picker.append(h('div', { class: 'row' }, input, dl, h('button', { class: 'btn', onclick: add }, 'Add'), batchSel,
    chosen.length ? h('button', { class: 'btn', onclick: () => setRuns([]) }, 'Clear') : null));
  picker.append(h('div', { style: { marginTop: '8px' } }, chosen.length ? chosen.map((id) => h('span', { class: 'chip' }, h('a', { href: `#/run/${enc(id)}` }, id),
    h('button', { title: 'remove', onclick: () => setRuns(chosen.filter((x) => x !== id)) }, '×'))) : h('span', { class: 'muted' }, 'Pick two or more runs, or add a whole batch.')));
  view.append(picker);
  if (!chosen.length) return;
  const details = await Promise.all(chosen.map((id) => api(`run/${enc(id)}`)));
  if (stale()) return;
  const variants = [...new Set(details.map((d) => d.summary.variant))];
  const distinct = variantColors(chosen);
  const vcolors = variantColors(variants);
  const oneEach = variants.length === chosen.length;
  const colorOf = (d, i) => (oneEach ? vcolors[d.summary.variant] : distinct[chosen[i]]);
  const label = (d) => (new Set(details.map((x) => x.summary.batch)).size > 1 ? `${d.summary.batch} ` : '') + runName(d.summary);

  const lines = (title, explain, pick, y, x) => h('section', { class: 'card' }, ...cardHead(title, null, explain), lineChart({
    series: details.map((d, i) => ({ name: label(d), color: colorOf(d, i), points: pick(d), id: d.summary.id })),
    height: 260, y, x: x || { time: true, min: 0, label: 'time since the run started' }, dots: 'auto',
    tooltip: (p, sr) => tipLines(sr.name, [p.text || `${fmt.score(p.y)}`, `at ${fmt.dur(p.x)}`]),
    onClick: (p, sr) => { if (p.k != null) go(`/run/${enc(sr.id)}/conversation`, { round: p.r, k: p.k }); else go('/run/' + enc(sr.id)); },
  }));
  const cum = (arr, f) => { let a = 0; return arr.map((x) => { a += f(x); return a; }); };
  view.append(h('div', { class: 'grid2' },
    lines('Progress score', 'Visible-test score after each round.', (d) => [{ x: 0, y: 0 }, ...d.summary.scores.visible.filter((v) => v.score != null).map((v) => ({ x: v.t, y: v.score, text: `round ${v.round}: ${fmt.score(v.score)}` }))], scoreAxis()),
    lines('Final score of each saved version', 'Hidden-test score of the version saved after each round.', (d) => d.summary.scores.hidden.filter((v) => v.score != null).map((v) => ({ x: v.t, y: v.score, text: `round ${v.round}: ${fmt.score(v.score)}` })), scoreAxis())));
  view.append(h('div', { class: 'grid2' },
    lines('Conversation size', 'Tokens the model read for each reply. Drops are conversation summaries.', (d) => d.digest.replies.map((r) => ({ x: r.t, y: r.in, k: r.k, r: r.r, text: `reply: read ${fmt.int(r.in)} tokens` })), { min: 0, format: fmt.compact }),
    lines('Tokens written, running total', 'Everything the model wrote, thinking included.', (d) => { const c = cum(d.digest.replies, (r) => r.out); return d.digest.replies.map((r, i) => ({ x: r.t, y: c[i], k: r.k, r: r.r, text: `${fmt.int(c[i])} tokens so far` })); }, { min: 0, format: fmt.compact })));
  view.append(h('div', { class: 'grid2' },
    lines('Tool calls, running total', 'Each step is one tool call.', (d) => { const c = cum(d.digest.calls.filter((x) => x.t != null), () => 1); return d.digest.calls.filter((x) => x.t != null).map((x, i) => ({ x: x.t, y: c[i], k: x.k, r: x.r, text: `${c[i]} calls · ${x.name}: ${String(x.cmd).slice(0, 80)}` })); }, { min: 0, format: fmt.int }),
    lines('Program code size', 'Lines of program code in the version saved after each round.', (d) => (d.code?.by_round || []).map((b, i) => ({ x: d.summary.scores.visible[i]?.t ?? i, y: b.totals['program code']?.lines || 0, text: `round ${b.round}: ${fmt.int(b.totals['program code']?.lines || 0)} lines` })), { min: 0, format: fmt.int })));

  const metric = (name, f, fmtf = fmt.int, title) => ({ name, f, fmtf, title });
  const rowsM = [
    metric('Variant', (d) => d.summary.variant, String),
    metric('Final score', (d) => d.summary.scores.final, fmt.score),
    metric('Progress score', (d) => d.summary.scores.visible_final, fmt.score),
    metric('Best final score during the run', (d) => d.summary.scores.best, fmt.score),
    metric('Rounds', (d) => d.summary.rounds),
    metric('Time used', (d) => d.summary.elapsed_s, fmt.dur),
    ...TIME_KINDS.map(([k, lbl]) => metric('  ' + lbl, (d) => d.digest.totals.time[k], fmt.dur)),
    metric('Replies', (d) => d.digest.totals.replies),
    metric('Tokens written', (d) => d.digest.totals.out),
    metric('  of which thinking', (d) => (d.reasoning?.status === 'ready' ? d.reasoning.total : null)),
    metric('Tokens read', (d) => d.digest.totals.in),
    metric('  re-used from memory', (d) => d.digest.totals.cached / (d.digest.totals.in || 1), (v) => fmt.pct(v, 1)),
    metric('Largest conversation (tokens)', (d) => d.digest.totals.conv_max),
    metric('Conversation summaries', (d) => d.digest.totals.summaries),
    metric('Tool calls', (d) => d.digest.totals.calls),
    metric('  failed', (d) => d.digest.totals.failed),
    metric('  blocked by the rule checker', (d) => d.digest.totals.blocked),
    metric('Shell commands', (d) => d.digest.totals.shell.calls),
    metric('File writes / edits / reads', (d) => `${d.digest.totals.files.writes} / ${d.digest.totals.files.edits} / ${d.digest.totals.files.reads}`, String),
    metric('Replies cut off at the length limit', (d) => d.digest.totals.cut_off),
    metric('Times the agent ended its turn', (d) => d.digest.totals.ended_turn),
    metric('Program code lines (final)', (d) => d.code?.final?.['program code']?.lines),
    metric('Test lines written by the agent', (d) => d.code?.final?.['tests written by the agent']?.lines ?? 0),
  ];
  const tb = h('tbody');
  for (const m of rowsM) {
    const vals = details.map((d) => { try { return m.f(d); } catch { return null; } });
    tb.append(h('tr', null, h('td', { style: { whiteSpace: 'pre' } }, m.name), vals.map((v) => h('td', { class: 'num' }, v == null ? '–' : m.fmtf(v)))));
  }
  view.append(h('section', { class: 'card' }, h('h3', null, 'Side by side'), h('div', { class: 'tablewrap' }, h('table', { class: 'data' },
    h('thead', null, h('tr', null, h('th', null, ''), details.map((d, i) => h('th', { class: 'num' }, h('span', { class: 'dot', style: { background: colorOf(d, i) } }), h('a', { href: `#/run/${enc(d.summary.id)}` }, label(d)))))), tb))));

  const ft = details.filter((d) => d.final_tests);
  if (ft.length) {
    const colsT = [...new Set(ft.flatMap((d) => d.final_tests.columns))];
    view.append(h('section', { class: 'card' }, h('h3', null, 'Final score on each hidden test'), heatmap({
      rows: ft.map((d) => ({ label: label(d), onClick: () => go(`/run/${enc(d.summary.id)}/tests`) })),
      cols: colsT.map((c) => c.replace(/^evidence\//, '').replace(/\.test$/, '')), colTitles: colsT,
      cells: ft.map((d) => colsT.map((c) => { const i = d.final_tests.columns.indexOf(c); return i < 0 ? null : d.final_tests.scores[i]; })),
    })));
  }
}

// ---------------------------------------------------------------- documents

async function docsPage(view) {
  const groups = await api('docs', { fresh: true });
  view.append(h('h1', null, 'Reports and documents'));
  view.append(h('p', { class: 'sub' }, 'The write-ups in docs/ and analysis/, and the study summaries under runs/study-results/.'));
  const grid = h('div', { class: 'grid2' });
  for (const g of groups) {
    if (!g.items.length) continue;
    grid.append(h('section', { class: 'card doclist' }, h('h3', null, g.title), g.items.map((it) =>
      h('a', { href: `#/doc/${it.path}` }, it.title, h('span', { class: 'faint small' }, `  ${it.path} · ${fmt.day(it.modified)}`)))));
  }
  view.append(grid);
}

async function docPage(view, path, params) {
  const d = await api(`doc?path=${enc(path)}`, { fresh: true });
  view.append(h('div', { class: 'crumbs' }, h('a', { href: '#/docs' }, 'Reports'), ' › ', path));
  const body = h('article', { class: 'doc card' });
  body.innerHTML = renderMarkdown(d.text, path);  // renderMarkdown escapes everything it is given
  view.append(h('p', { class: 'small faint' }, `last changed ${fmt.when(d.modified)}`), body);
  const at = params.get('at');
  view.afterMount = () => {
    if (at) { const el = document.getElementById(at); if (el) el.scrollIntoView(); } else window.scrollTo(0, 0);
  };
}

// ---------------------------------------------------------------- model server

async function serverPage(view) {
  const d = await api('server', { fresh: true });
  view.append(h('h1', null, 'Model server'));
  const st = d.status;
  view.append(h('p', { class: 'sub' }, st.running ? h('span', { class: 'good' }, `Running (process ${st.pid}).`) : h('span', { class: 'warn' }, 'Not running.'),
    st.launch ? ` Current configuration: launch ${st.launch}.` : '', d.doc ? h('span', null, ' Notes on every configuration: ', h('a', { href: `#/doc/${d.doc}` }, d.doc)) : null));
  view.append(h('p', { class: 'explain' }, 'Each launch of the inference server is recorded under runs/inference/. Secret settings are hidden. The server log is not shown here.'));
  for (const l of d.launches) {
    const info = Object.entries(l.info || {});
    view.append(h('section', { class: 'card' },
      h('div', { class: 'card-head' }, h('h3', null, l.name), l.name === st.launch ? pill('current', 'good') : null),
      info.length ? h('table', { class: 'kv' }, h('tbody', null, info.map(([k, v]) => h('tr', null, h('td', null, k), h('td', { class: 'mono' }, v))))) : null,
      l.config ? h('details', null, h('summary', { class: 'small muted' }, 'server settings (config.yaml)'), h('pre', { class: 'codebox' }, l.config)) : null));
  }
}

render();
