// One run: overview, conversation, files, tests, tool use, setup.

import {
  h, clear, api, forget, fmt, enc, END, STOP, TASK, STATUS, PROFILE, FAILURE, TIME_KINDS, CODE_KINDS, card, cardHead,
  segmented, table, runName, statusPill, pill, kpi, sum, errorBox, toolColor, tipLines, plural, lazyDetails, scoreBar,
  scoreCell, activityText, heatColor, add, END_SHORT,
} from './util.js';
import { lineChart, barChart, heatmap, timeline, scoreAxis } from './charts.js';
import { renderMarkdown } from './markdown.js';

const TABS = [
  ['overview', 'Overview'],
  ['conversation', 'Conversation'],
  ['files', 'Files it wrote'],
  ['tests', 'Test results'],
  ['tools', 'Tool use and behaviour'],
  ['setup', 'Setup'],
];
const STOP_COLORS = { toolUse: 'var(--c-model)', stop: '#f59e0b', length: 'var(--bad)', error: 'var(--bad)', aborted: 'var(--bad)' };

export async function runPage(view, id, tab, params, stale, ctx) {
  const data = await api(`run/${enc(id)}`);
  const S = data.summary;
  const D = data.digest;
  const T = D.totals;
  const live = S.status === 'running' || S.status === 'scoring';

  view.append(h('div', { class: 'crumbs' }, h('a', { href: '#/' }, 'Batches'), ' › ',
    h('a', { href: `#/batch/${S.batch}` }, S.batch), ' › ', id));
  view.append(h('div', { class: 'row' }, h('h1', null, runName(S)), statusPill(S),
    S.profile === 'pilot' ? pill('trial run') : null, S.resumed ? pill('resumed after an interruption', 'warn') : null,
    h('span', { class: 'spacer' }),
    h('a', { class: 'small', href: `#/compare?runs=${enc(id)}` }, 'Compare with other runs →')));
  const ended = S.status === 'finished' ? (END[S.end_reason] || S.end_reason || '') : (STATUS[S.status] || S.status);
  view.append(h('p', { class: 'sub' },
    `${TASK[S.task] || S.task} · ${S.language}${S.framework ? ' (' + S.framework + ')' : ''} · started ${fmt.when(S.started_at)} · `,
    `${fmt.dur(S.elapsed_s)} of ${S.budget_hours ?? '?'} h · ${plural(S.rounds, 'round')} · ended: ${ended}`));
  if (S.variant_description) view.append(h('p', { class: 'explain' }, 'Variant: ', S.variant_description));
  if (live) {
    const line = h('div', { class: 'notice' }, 'This run is going on now. Checking what it is doing…');
    view.append(line);
    const tick = () => api(`run/${enc(id)}/activity`, { fresh: true }).then((a) => { line.textContent = activityText(a) + ' · this page reloads every 30 seconds'; }).catch(() => {});
    tick();
    const t1 = setInterval(tick, 5000);
    const t2 = setInterval(() => { if (!stale()) { forget(`run/${enc(id)}`); window.dispatchEvent(new HashChangeEvent('hashchange')); } }, 30000);
    ctx.onLeave(() => { clearInterval(t1); clearInterval(t2); });
  }

  const reasoning = data.reasoning || {};
  const thinkingTotal = reasoning.status === 'ready' ? reasoning.total : null;
  const sc = S.scores;
  view.append(h('div', { class: 'kpis' },
    kpi('Final score', scoreCell(sc.final, sc.final_frozen), sc.final_round != null ? `hidden tests, version after round ${sc.final_round}` : 'hidden tests', sc.final == null ? '' : sc.final >= 0.5 ? 'good' : sc.final > 0.05 ? 'warn' : 'bad'),
    kpi('Progress score', fmt.score(sc.visible_final), `visible tests; best ${fmt.score(sc.visible_best)}`),
    sc.fuzz ? kpi('Random-program check', fmt.score(sc.fuzz.final), 'compared against GCC') : kpi('Best final score', fmt.score(sc.best), 'any saved version'),
    kpi('Replies', fmt.int(T.replies), `${fmt.int(T.cut_off)} cut off · ${fmt.int(T.ended_turn)} ended the turn`),
    kpi('Tokens written', fmt.compact(T.out), thinkingTotal != null ? `${fmt.pct(thinkingTotal / (T.out || 1))} thinking` : `thinking ${reasoning.status === 'counting' ? 'being counted…' : 'not counted'}`),
    kpi('Tokens read', fmt.compact(T.in), `${fmt.pct(T.cached / (T.in || 1))} re-used from memory`),
    kpi('Tool calls', fmt.int(T.calls), `${fmt.int(T.failed)} failed · ${fmt.int(T.blocked)} blocked`),
    kpi('Conversation summaries', fmt.int(T.summaries), `${fmt.dur(T.time.summaries)} spent summarizing`),
    kpi('Program code', `${fmt.int(data.code?.final?.['program code']?.lines ?? 0)} lines`, `${fmt.int(data.code?.final?.['tests written by the agent']?.lines ?? 0)} lines of its own tests`)));

  const tabs = h('nav', { class: 'tabs' }, TABS.map(([key, label]) => h('a', { href: `#/run/${enc(id)}/${key}`, class: key === tab ? 'on' : '' }, label)));
  view.append(tabs);
  const body = h('div');
  view.append(body);
  const env = { id, data, S, D, T, params, stale, ctx, view };
  if (reasoning.status === 'counting') {
    const t = setInterval(async () => {
      try {
        const r = await api(`run/${enc(id)}/reasoning`, { fresh: true });
        if (r.status !== 'counting') { clearInterval(t); if (!stale()) { forget(`run/${enc(id)}`); window.dispatchEvent(new HashChangeEvent('hashchange')); } }
      } catch { clearInterval(t); }
    }, 2500);
    ctx.onLeave(() => clearInterval(t));
  }
  if (tab === 'overview') overviewTab(body, env);
  else if (tab === 'conversation') await conversationTab(body, env);
  else if (tab === 'files') await filesTab(body, env);
  else if (tab === 'tests') await testsTab(body, env);
  else if (tab === 'tools') toolsTab(body, env);
  else if (tab === 'setup') await setupTab(body, env);
  else body.append(h('p', null, 'No such tab.'));
}

function convoLink(id, r, k) { return `#/run/${enc(id)}/conversation?round=${r}&k=${k}`; }

function lookups(D) {
  const replyByK = new Map(D.replies.map((r, i) => [r.k, { ...r, n: i + 1, i }]));
  const callByK = new Map(D.calls.filter((c) => c.k != null).map((c) => [c.k, c]));
  const summaryByK = new Map(D.summaries.map((x, i) => [x.k, { ...x, n: i + 1 }]));
  return { replyByK, callByK, summaryByK };
}

// ---------------------------------------------------------------- overview

function overviewTab(el, env) {
  const { id, data, S, D, T, ctx } = env;
  const sc = S.scores;
  const reasoning = data.reasoning || {};
  const perReply = reasoning.status === 'ready' && reasoning.aligned ? reasoning.per_reply : null;
  const { replyByK, callByK, summaryByK } = lookups(D);
  const go = ctx.go;

  // scores
  const vis = sc.visible.filter((v) => v.score != null);
  const hid = sc.hidden.filter((v) => v.score != null);
  const series = [
    { name: 'Progress score (visible tests)', color: 'var(--c-model)', points: vis.map((v) => ({ x: v.t, y: v.score, round: v.round, built: v.built, hollow: v.built === false, mark: v.built === false })) },
  ];
  if (hid.length) series.push({ name: 'Final score (hidden tests)', color: '#16a34a', points: hid.map((v) => ({ x: v.t, y: v.score, round: v.round, frozen: v.frozen })) });
  if (sc.fuzz && sc.fuzz.final != null) {
    const t = (hid.find((v) => v.round === sc.fuzz.round) || hid[hid.length - 1] || {}).t;
    series.push({ name: 'Random-program check', color: '#d97706', noLine: true, points: [{ x: t, y: sc.fuzz.final, round: sc.fuzz.round }] });
  }
  const scoreChart = lineChart({
    series, height: 250, y: scoreAxis(), x: { time: true, min: 0, max: Math.max(S.elapsed_s || 0, ...vis.map((v) => v.t || 0)), label: 'time since the run started' }, dots: true,
    tooltip: (p, sr) => tipLines(`${sr.name}`, [`version after round ${p.round}: ${fmt.score(p.y)}`, p.built === false ? 'this version did not build' : null, p.frozen != null ? `(corrected; recorded at the time: ${fmt.score(p.frozen)})` : null, `at ${fmt.dur(p.x)}`, 'click to see the test results']),
    onClick: (p, sr) => go(`/run/${enc(id)}/tests`, { set: sr.name.startsWith('Progress') ? 'visible' : 'hidden', round: p.round }),
  });
  el.append(h('section', { class: 'card' }, ...cardHead('Scores after each round', null,
    'The harness saves the workspace after every round and scores that version. Progress score: visible tests (the agent never saw them in this setup unless its variant gave access). Final score: hidden tests, which decide the result. Hollow red points did not build.'), scoreChart));

  // activity lanes
  const lanes = D.rounds.map((r) => ({ label: `Round ${r.round}`, start: r.start, end: r.end }));
  const segs = [];
  let li = 0;
  for (const [a, b, kind, k] of D.segments) {
    if (a == null || !lanes.length) continue;
    while (li + 1 < lanes.length && a >= lanes[li + 1].start - 1) li++;
    segs.push({ lane: li, start: a, end: b ?? a, kind, k });
  }
  const colors = { model: 'var(--c-model)', tool: 'var(--c-tools)', summary: 'var(--c-summaries)', lost: 'var(--c-lost)', gap: 'var(--c-startup)' };
  const tl = timeline({
    lanes, segments: segs, colors,
    tooltip: (seg) => {
      const len = fmt.dur(seg.end - seg.start);
      if (seg.kind === 'model') {
        const r = replyByK.get(seg.k) || {};
        const th = perReply ? perReply[r.i] : null;
        return tipLines(`Reply ${r.n} · round ${r.r}`, [`writing took ${len}`, `wrote ${fmt.int(r.out)} tokens${th != null ? ` (${fmt.int(th)} thinking)` : ''}`, `read ${fmt.int(r.in)} tokens`, `then: ${r.tools && r.tools.length ? 'called ' + r.tools.join(', ') : STOP[r.stop] || r.stop}`, 'click to read it']);
      }
      if (seg.kind === 'tool') {
        const c = callByK.get(seg.k) || {};
        return tipLines(`${c.name || 'tool'} · ${len}`, [String(c.cmd || '').slice(0, 300), c.err ? `FAILED: ${c.why}` : null, 'click to read it']);
      }
      if (seg.kind === 'summary') {
        const x = summaryByK.get(seg.k) || {};
        return tipLines(`Conversation summary ${x.n}`, [`took ${len}`, `conversation was ${fmt.int(x.before)} tokens`, `summary written: ${fmt.int(x.written)} tokens`]);
      }
      if (seg.kind === 'gap') {
        const r = replyByK.get(seg.k) || {};
        return tipLines(`Nothing saved for ${len}`, [`before reply ${r.n} began: start-up, a retried request, or waiting on the model server`, 'click to open the reply that followed']);
      }
      return tipLines('Lost at the end of the round', [`${len} of work that was cut off by the round time limit and never saved`]);
    },
    onClick: (seg) => { const r = replyByK.get(seg.k) || callByK.get(seg.k) || summaryByK.get(seg.k); go(`/run/${enc(id)}/conversation`, { round: r ? r.r : 0, k: seg.k }); },
  });
  el.append(h('section', { class: 'card' }, ...cardHead('What happened, minute by minute', null,
    'One lane per round, from the round’s start. Blue: the model writing a reply. Green: a tool running (a shell command, a file read or write). Purple: the conversation being summarized to make room. Red: work in progress when the round was cut off. Grey: nothing was saved for more than 20 seconds (start-up, a retried request, or waiting on the server). Hover for details, click to open that moment in the conversation.'), tl,
    h('div', { class: 'legend' }, [['Model writing', colors.model], ['Tool running', colors.tool], ['Summarizing', colors.summary], ['Lost at round end', colors.lost], ['Nothing saved for over 20 s', colors.gap], ['Short hand-overs between steps', 'var(--grid)']].map(([n, c]) => h('span', { class: 'item' }, h('span', { class: 'swatch', style: { background: c } }), n)))));

  // conversation size and tokens per reply
  const markers = D.summaries.map((x) => ({ x: x.t }));
  const hl = [];
  if (S.context_window) hl.push({ y: S.context_window, label: `model's limit ${fmt.int(S.context_window)}`, color: 'var(--bad)', fit: true });
  const sizeChart = lineChart({
    series: [{ name: 'conversation read', color: 'var(--c-model)', points: D.replies.map((r) => ({ x: r.t, y: r.in, k: r.k, r: r.r, c: r.c })) }],
    height: 240, y: { min: 0, format: fmt.compact }, x: { time: true, min: 0, label: 'time since the run started' }, markers, hlines: hl, legend: false, dots: false,
    tooltip: (p) => tipLines(`Reply ${replyByK.get(p.k)?.n} · round ${p.r}`, [`read ${fmt.int(p.y)} tokens`, `${fmt.pct(p.c / (p.y || 1))} re-used from memory`, 'click to open']),
    onClick: (p) => go(`/run/${enc(id)}/conversation`, { round: p.r, k: p.k }),
  });
  const outSeries = [{ name: 'tokens written', color: 'var(--c-answer)', bars: true, points: D.replies.map((r) => ({ x: r.t, y: r.out, k: r.k, r: r.r, stop: r.stop, color: r.stop === 'toolUse' ? null : STOP_COLORS[r.stop] })) }];
  if (perReply) outSeries.push({ name: 'of which thinking', color: 'var(--c-thinking)', noLine: true, r: 2, points: D.replies.map((r, i) => ({ x: r.t, y: perReply[i], k: r.k, r: r.r, stop: r.stop, total: r.out })) });
  const hl2 = [];
  if (S.reply_cap) hl2.push({ y: S.reply_cap, label: `reply limit ${fmt.int(S.reply_cap)}`, color: 'var(--bad)' });
  if (S.thinking_budget) hl2.push({ y: S.thinking_budget, label: `thinking limit ${fmt.int(S.thinking_budget)}`, color: 'var(--c-thinking)' });
  const outChart = lineChart({
    series: outSeries, height: 240, y: { min: 0, format: fmt.compact }, x: { time: true, min: 0, label: 'time since the run started' }, hlines: hl2, dots: false,
    tooltip: (p, sr) => { const r = replyByK.get(p.k) || {}; return tipLines(`Reply ${r.n} · round ${p.r}`, [`wrote ${fmt.int(r.out)} tokens`, perReply ? `thinking ${fmt.int(perReply[r.i])}` : null, `then: ${STOP[p.stop] || p.stop}`, `writing took ${fmt.dur(r.d)}`, 'click to open']); },
    onClick: (p) => go(`/run/${enc(id)}/conversation`, { round: p.r, k: p.k }),
  });
  el.append(h('div', { class: 'grid2' },
    h('section', { class: 'card' }, ...cardHead('Conversation size', null, 'How much the model read for each reply: the whole conversation so far. Dashed purple lines are conversation summaries, which shrink it.'), sizeChart),
    h('section', { class: 'card' }, ...cardHead('Tokens written per reply', null, `Each bar is one reply (orange: the agent ended its turn; red: cut off at the length limit).${perReply ? ' Purple dots: the part that was thinking.' : ' Thinking: ' + (data.tokenizer || 'not counted') + '.'}`), outChart)));

  // time by round
  const tb = barChart({
    categories: D.rounds.map((r) => `Round ${r.round}`), format: fmt.dur, time: true,
    series: TIME_KINDS.map(([k, label, color]) => ({ name: label, color, values: D.rounds.map((r) => r.time[k] || 0) })),
    tooltip: (i) => { const t = D.rounds[i].time; const all = sum(Object.values(t)); return tipLines(`Round ${D.rounds[i].round}`, TIME_KINDS.map(([k, label]) => `${label}: ${fmt.dur(t[k])} (${fmt.pct(t[k] / (all || 1))})`)); },
    labelWidth: 90,
  });
  const allT = sum(Object.values(T.time));
  el.append(h('section', { class: 'card' }, ...cardHead('Where the time went', null,
    `Across the run: ${TIME_KINDS.map(([k, label]) => `${label.toLowerCase()} ${fmt.pct(T.time[k] / (allT || 1))}`).join(', ')}. The model wrote ${fmt.int(T.tokens_per_min)} tokens per minute of writing.`), tb));

  // rounds table
  const byRoundCode = new Map((data.code?.by_round || []).map((b) => [b.round, b]));
  const visByRound = new Map(sc.visible.map((v) => [v.round, v]));
  const hidByRound = new Map(sc.hidden.map((v) => [v.round, v]));
  const rows = D.rounds.map((r) => ({ ...r, vis: visByRound.get(r.round), hid: hidByRound.get(r.round), code: byRoundCode.get(r.round) }));
  el.append(h('section', { class: 'card' }, h('h3', null, 'Rounds'), table([
    { key: 'round', label: 'Round', num: true },
    { key: 'start', label: 'Started', render: (r) => fmt.clock(D.t0 + r.start * 1000), sort: (r) => r.start },
    { key: 'len', label: 'Length', num: true, render: (r) => fmt.dur(r.end - r.start), sort: (r) => r.end - r.start },
    { key: 'how', label: 'How it ended', render: (r) => (r.open ? 'still going' : r.capped ? 'cut off at the time limit' : r.returncode === 0 ? 'the agent stopped' : `agent exited (${r.returncode})`), nosort: true },
    { key: 'vis', label: 'Progress', num: true, render: (r) => (r.vis ? h('span', { class: r.vis.built === false ? 'bad' : '' }, fmt.score(r.vis.score), r.vis.built === false ? ' (no build)' : '') : '–'), sort: (r) => r.vis?.score },
    { key: 'hid', label: 'Final', num: true, render: (r) => (r.hid ? scoreCell(r.hid.score, r.hid.frozen) : '–'), sort: (r) => r.hid?.score },
    { key: 'replies', label: 'Replies', num: true },
    { key: 'calls', label: 'Tool calls', num: true, render: (r) => `${r.calls}${r.failed ? ` (${r.failed} failed)` : ''}`, sort: (r) => r.calls },
    { key: 'summaries', label: 'Summaries', num: true },
    { key: 'out', label: 'Tokens written', num: true, render: (r) => fmt.int(r.out) },
    { key: 'lines', label: 'Lines +/−', num: true, render: (r) => (r.code ? `+${fmt.int(r.code.added)} / −${fmt.int(r.code.removed)}` : '–'), sort: (r) => r.code?.added },
    { key: 'prog', label: 'Program lines', num: true, render: (r) => fmt.int(r.code?.totals?.['program code']?.lines), sort: (r) => r.code?.totals?.['program code']?.lines },
  ], rows, { sortKey: 'round', sortDir: 1, onRow: (r) => go(`/run/${enc(id)}/conversation`, { round: r.round }) })));
}

// ---------------------------------------------------------------- conversation

async function conversationTab(el, env) {
  const { id, D, params, ctx, data } = env;
  const rounds = D.rounds.map((r) => r.round);
  const round = params.has('round') ? Number(params.get('round')) : rounds[0] ?? 0;
  const target = params.has('k') ? Number(params.get('k')) : null;
  const convo = await api(`run/${enc(id)}/conversation?round=${round}`);
  const { replyByK, callByK } = lookups(D);
  const reasoning = data.reasoning || {};
  const perReply = reasoning.status === 'ready' && reasoning.aligned ? reasoning.per_reply : null;
  const opts = { thinking: params.get('thinking') === '1', problems: params.get('problems') === '1', tool: params.get('tool') || '' };

  const side = h('aside', { class: 'convo-side' });
  const roundList = h('div', { class: 'rounds' }, D.rounds.map((r) => h('a', { href: `#/run/${enc(id)}/conversation?round=${r.round}`, class: r.round === round ? 'on' : '' },
    h('span', null, `Round ${r.round}`), h('span', { class: 'faint small' }, `${r.replies} replies · ${fmt.dur(r.end - r.start)}`))));
  side.append(h('section', { class: 'card' }, h('h3', null, 'Rounds'), roundList));
  const setOpt = (k, v) => { const p = new URLSearchParams(params); if (v) p.set(k, v); else p.delete(k); p.delete('k'); ctx.go(`/run/${enc(id)}/conversation`, Object.fromEntries(p)); };
  const toolNames = Object.keys(env.T.by_tool);
  side.append(h('section', { class: 'card' }, h('h3', null, 'Show'),
    h('div', { class: 'opts' },
      h('label', { class: 'check' }, h('input', { type: 'checkbox', checked: opts.thinking, onchange: (e) => setOpt('thinking', e.target.checked ? '1' : '') }), 'open all thinking'),
      h('label', { class: 'check' }, h('input', { type: 'checkbox', checked: opts.problems, onchange: (e) => setOpt('problems', e.target.checked ? '1' : '') }), 'only problems (failed calls, cut-off or final replies)'),
      h('select', { class: 'pick', onchange: (e) => setOpt('tool', e.target.value) }, h('option', { value: '' }, 'all tools'),
        toolNames.map((t) => h('option', { value: t, selected: t === opts.tool }, `only ${t} calls`))))));
  const q = h('input', { class: 'pick', type: 'search', placeholder: 'Search the whole run…', style: { width: '100%' } });
  const hits = h('div', { class: 'hits' });
  const doSearch = async () => {
    const text = q.value.trim();
    clear(hits);
    if (text.length < 2) return;
    hits.append(h('div', { class: 'muted small' }, 'Searching…'));
    try {
      const res = await api(`run/${enc(id)}/search?q=${enc(text)}`, { fresh: true });
      clear(hits);
      hits.append(h('div', { class: 'muted small' }, `${fmt.int(res.total)} matches${res.total > res.shown ? `, first ${res.shown} shown` : ''}`));
      for (const hit of res.hits) {
        hits.append(h('div', { class: 'hit', onclick: () => ctx.go(`/run/${enc(id)}/conversation`, { round: hit.r, k: hit.k, q: text }) },
          h('div', { class: 'faint' }, `round ${hit.r} · ${hit.where}`), hit.before, h('mark', null, hit.match), hit.after));
      }
    } catch (e) { clear(hits); hits.append(errorBox(e)); }
  };
  q.addEventListener('keydown', (e) => { if (e.key === 'Enter') doSearch(); });
  if (params.get('q')) { q.value = params.get('q'); setTimeout(doSearch, 0); }
  side.append(h('section', { class: 'card' }, h('h3', null, 'Search'), q, hits));

  const list = h('div', { class: 'convo' });
  const byCallId = new Map();
  for (const e of convo.entries) if (e.kind === 'reply') for (const c of e.calls) byCallId.set(c.id, c);
  let shown = 0;
  for (const e of convo.entries) {
    if (!keep(e, opts, byCallId)) continue;
    list.append(entryCard(e, { id, replyByK, callByK, perReply, opts, t0: convo.t0, byCallId, highlight: params.get('q') }));
    shown++;
  }
  if (!shown) list.append(h('p', { class: 'muted' }, 'Nothing in this round matches the filters.'));
  const r = D.rounds.find((x) => x.round === round);
  const head = h('div', { class: 'row', style: { marginBottom: '8px' } }, h('h2', { style: { margin: 0 } }, `Round ${round}`),
    r ? h('span', { class: 'muted' }, `${fmt.clock(D.t0 + r.start * 1000)} · ${fmt.dur(r.end - r.start)} · ${r.replies} replies · ${r.calls} tool calls · ${r.summaries} summaries${r.capped ? ' · cut off at the time limit' : ''}`) : null);
  el.append(h('div', { class: 'convo-layout' }, side, h('div', null, head, list)));
  if (target != null) {
    env.view.afterMount = () => {
      const node = document.getElementById('e-' + target);
      if (node) {
        for (const d of node.querySelectorAll('details')) if (!d.open) { d.open = true; d.dispatchEvent(new Event('toggle')); }
        node.scrollIntoView({ block: 'start' });
        node.classList.add('flash');
        setTimeout(() => node.classList.remove('flash'), 2500);
      }
    };
  }
}

function keep(e, opts, byCallId) {
  if (opts.tool) {
    if (e.kind === 'reply') return e.calls.some((c) => c.name === opts.tool);
    if (e.kind === 'result') return e.name === opts.tool;
    return false;
  }
  if (opts.problems) {
    if (e.kind === 'result') return e.err;
    if (e.kind === 'reply') return e.stop !== 'toolUse';
    return e.kind === 'summary' ? false : e.kind !== 'note';
  }
  return true;
}

function marked(text, q) {
  if (!q) return text;
  const low = text.toLowerCase(), ql = q.toLowerCase();
  const out = [];
  let i = 0;
  let at = low.indexOf(ql);
  let n = 0;
  while (at >= 0 && n < 200) {
    out.push(text.slice(i, at), h('mark', null, text.slice(at, at + q.length)));
    i = at + q.length;
    at = low.indexOf(ql, i);
    n++;
  }
  out.push(text.slice(i));
  return out;
}

function fullButton(id, k, label, onText) {
  const b = h('button', { class: 'btn', type: 'button' }, label);
  b.addEventListener('click', async () => {
    b.disabled = true;
    b.textContent = 'Loading…';
    try { onText(await api(`run/${enc(id)}/entry?k=${k}`)); b.remove(); } catch (e) { b.replaceWith(errorBox(e)); }
  });
  return b;
}

function entryCard(e, c) {
  const { id, replyByK, callByK, perReply, opts, byCallId, highlight } = c;
  const card = h('div', { class: `entry ${e.kind}${e.kind === 'result' && e.err ? ' err' : ''}`, id: 'e-' + e.k });
  const pre = (text, cls) => h('pre', { class: cls || null }, marked(text, highlight));
  if (e.kind === 'prompt') {
    add(card, h('div', { class: 'ehead' }, h('span', { class: 'who' }, 'Prompt from the harness'), h('span', null, fmt.clock(e.t)), h('span', null, `${fmt.int(e.full || e.text.length)} characters`)));
    add(card, e.text.length > 600 ? lazyDetails(`show the prompt (${e.text.split('\n').length} lines)`, () => pre(e.text)) : pre(e.text));
    return card;
  }
  if (e.kind === 'note') { add(card, h('span', null, fmt.clock(e.t), ' · ', e.text)); return card; }
  if (e.kind === 'summary') {
    add(card, h('div', { class: 'ehead' }, h('span', { class: 'who' }, 'Conversation summarized'), h('span', null, fmt.clock(e.t)),
      h('span', null, `conversation was ${fmt.int(e.before)} tokens · summary ${fmt.int(e.written)} tokens written · took ${fmt.dur(e.d)}`)));
    add(card, lazyDetails('read the summary the model continued from', () => pre(e.text), { open: opts.thinking }));
    return card;
  }
  if (e.kind === 'result') {
    const call = byCallId.get(e.id);
    const meta = callByK.get(e.k);
    add(card, h('div', { class: 'ehead' }, h('span', { class: 'who' }, `Result of ${e.name}`), h('span', null, fmt.clock(e.t)), h('span', null, `took ${fmt.dur(e.d)}`),
      e.err ? h('span', { class: 'bad' }, `failed: ${meta?.why || 'error'}`) : null, h('span', { class: 'spacer' }), h('span', { class: 'faint' }, `${fmt.int(e.full || e.text.length)} characters`)));
    const lines = e.text.split('\n');
    const short = lines.length <= 14 && e.text.length <= 1500;
    if (short) add(card, pre(e.text || '(no output)'));
    else {
      add(card, pre(lines.slice(0, 8).join('\n') + '\n…'));
      add(card, lazyDetails(`show all ${fmt.int(lines.length)} lines`, () => {
        const box = h('div', null, pre(e.text));
        if (e.full) add(box, fullButton(id, e.k, `load the rest (${fmt.int(e.full)} characters in all)`, (full) => { box.replaceChildren(pre(full.text)); }));
        return box;
      }));
    }
    void call;
    return card;
  }
  // reply
  const r = replyByK.get(e.k) || {};
  const th = perReply && r.i != null ? perReply[r.i] : null;
  add(card, h('div', { class: 'ehead' },
    h('span', { class: 'who' }, `Reply ${r.n ?? ''}`), h('span', null, fmt.clock(e.t)), h('span', null, `took ${fmt.dur(e.d)}`),
    h('span', null, `wrote ${fmt.int(e.out)} tokens${th != null ? ` (${fmt.int(th)} thinking)` : ''}`),
    h('span', null, `read ${fmt.int(e.in)} (${fmt.pct(e.c / (e.in || 1))} re-used)`),
    h('span', { class: 'spacer' }),
    e.stop !== 'toolUse' ? pill(STOP[e.stop] || e.stop, e.stop === 'stop' ? 'warn' : 'bad') : null));
  if (e.error) add(card, h('div', { class: 'bad small' }, e.error));
  if (e.thinking.text) {
    const summaryText = `thinking — ${fmt.int(e.thinking.full || e.thinking.text.length)} characters${e.thinking.full ? ' (long)' : ''}`;
    add(card, lazyDetails(summaryText, () => {
      const box = h('div', null, pre(e.thinking.text));
      if (e.thinking.full) add(box, fullButton(id, e.k, 'load all of it', (full) => box.replaceChildren(pre(full.thinking.text))));
      return box;
    }, { open: opts.thinking }));
  }
  if (e.text.text && e.text.text.trim()) add(card, h('div', { class: 'text' }, marked(e.text.text.trim(), highlight)));
  for (const call of e.calls) add(card, callView(call, e, id, highlight));
  return card;
}

function callView(call, entry, id, highlight) {
  const a = call.args || {};
  const box = h('div', { class: 'call' });
  const pre = (text, cls) => h('pre', { class: cls || null }, marked(String(text ?? ''), highlight));
  if (call.name === 'bash') {
    add(box, h('span', { class: 'cname' }, 'bash'), a.timeout ? h('span', { class: 'faint small' }, ` (time limit ${a.timeout} s)`) : null, pre('$ ' + (a.command || '')));
  } else if (call.name === 'write') {
    const content = String(a.content ?? '');
    add(box, h('span', { class: 'cname' }, 'write '), h('span', { class: 'mono' }, a.path || a.file_path || ''),
      h('span', { class: 'faint small' }, `  ${fmt.int(content.split('\n').length)} lines, ${fmt.int(call.full || content.length)} characters`));
    add(box, lazyDetails('show what it wrote', () => {
      const b = h('div', null, pre(content));
      if (call.full) add(b, fullButton(id, entry.k, 'load the whole file', (full) => { const c2 = full.calls.find((x) => x.id === call.id); b.replaceChildren(pre(c2?.args?.content)); }));
      return b;
    }));
  } else if (call.name === 'edit') {
    const edits = Array.isArray(a.edits) ? a.edits : [a];
    add(box, h('span', { class: 'cname' }, 'edit '), h('span', { class: 'mono' }, a.path || a.file_path || ''), h('span', { class: 'faint small' }, `  ${plural(edits.length, 'change')}`));
    edits.forEach((ed, i) => {
      const oldT = String(ed.oldText ?? ed.old_string ?? ''), newT = String(ed.newText ?? ed.new_string ?? '');
      add(box, lazyDetails(`change ${i + 1}: replace ${plural(oldT.split('\n').length, 'line')} with ${plural(newT.split('\n').length, 'line')}`,
        () => h('div', { class: 'diffpair' }, pre(oldT, 'old'), pre(newT, 'new'))));
    });
  } else if (call.name === 'read') {
    add(box, h('span', { class: 'cname' }, 'read '), h('span', { class: 'mono' }, a.path || a.file_path || ''),
      a.offset || a.limit ? h('span', { class: 'faint small' }, `  ${a.offset ? 'from line ' + a.offset : ''}${a.limit ? ' · ' + a.limit + ' lines' : ''}`) : null);
  } else {
    add(box, h('span', { class: 'cname' }, call.name), pre(JSON.stringify(a, null, 2)));
  }
  return box;
}

// ---------------------------------------------------------------- files

async function filesTab(el, env) {
  const { id, params, ctx } = env;
  const files = await api(`run/${enc(id)}/files`);
  if (!files.rounds.length) { el.append(h('p', { class: 'muted' }, 'No saved versions yet.')); return; }
  const rounds = files.rounds.map((r) => r.round);
  const round = params.has('round') ? Number(params.get('round')) : rounds[rounds.length - 1];
  const R = files.rounds.find((r) => r.round === round) || files.rounds[files.rounds.length - 1];
  const path = params.get('path') || (R.files.find((f) => f[0] === files.entry) || R.files.find((f) => f[1] === 'program code') || [])[0];
  const mode = params.get('view') || 'file';
  const diff = await api(`run/${enc(id)}/diff?round=${R.round}`).catch(() => ({ files: [] }));
  const changed = new Map(diff.files.map((f) => [f.path, f]));
  const nav = (p) => ctx.go(`/run/${enc(id)}/files`, Object.fromEntries(Object.entries({ round: R.round, path, view: mode, ...p }).filter(([, v]) => v != null && v !== '')));

  // size by round
  const kinds = CODE_KINDS.filter(([k]) => files.rounds.some((r) => r.totals[k]));
  el.append(h('section', { class: 'card' }, ...cardHead('Size of what it wrote, round by round', null, 'Lines in the version saved after each round, by kind of file. Click a bar to look at that version.'),
    barChart({
      categories: files.rounds.map((r) => `round ${r.round}`), horizontal: false, height: 200, format: fmt.int,
      series: kinds.map(([k, color]) => ({ name: k, color, values: files.rounds.map((r) => r.totals[k]?.lines || 0) })),
      onClick: (i) => nav({ round: files.rounds[i].round }),
      tooltip: (i) => tipLines(`version after round ${files.rounds[i].round}`, [...Object.entries(files.rounds[i].totals).map(([k, v]) => `${k}: ${fmt.int(v.lines)} lines, ${plural(v.files, 'file')}`), `changed this round: +${fmt.int(files.rounds[i].added)} / −${fmt.int(files.rounds[i].removed)} lines in ${plural(files.rounds[i].changed || 0, 'file')}`]),
    })));

  const roundPick = h('select', { class: 'pick', onchange: (e) => nav({ round: e.target.value }) }, rounds.map((r) => h('option', { value: r, selected: r === R.round }, `version after round ${r}`)));
  const rowsF = R.files.map(([p, kind, bytes, lines, sha]) => ({ p, kind, bytes, lines, sha, ch: changed.get(p) }));
  const listCard = h('section', { class: 'card files-list' },
    h('div', { class: 'row' }, roundPick, h('span', { class: 'muted small' }, `${plural(R.files.length, 'file')} · +${fmt.int(R.added)} / −${fmt.int(R.removed)} lines this round`)),
    h('div', { style: { marginTop: '8px' } }, table([
      { key: 'p', label: 'File', render: (f) => h('span', { class: 'mono' }, f.p) },
      { key: 'kind', label: 'Kind', render: (f) => h('span', { class: 'small muted nowrap' }, f.kind) },
      { key: 'lines', label: 'Lines', num: true, render: (f) => fmt.int(f.lines) },
      { key: 'ch', label: 'This round', num: true, render: (f) => (f.ch ? h('span', null, h('span', { class: 'good' }, '+' + f.ch.added), ' ', h('span', { class: 'bad' }, '−' + f.ch.removed)) : ''), sort: (f) => (f.ch ? Number(f.ch.added) + Number(f.ch.removed) : -1) },
    ], rowsF, { sortKey: 'kind', sortDir: 1, onRow: (f) => nav({ path: f.p }), rowClass: (f) => (f.p === path ? 'on' : '') })));
  const deleted = diff.files.filter((f) => !R.files.some((x) => x[0] === f.path));
  if (deleted.length) listCard.append(h('p', { class: 'small muted' }, 'Removed this round: ', deleted.map((f) => f.path).join(', ')));

  const viewer = h('section', { class: 'card viewer' });
  if (path) {
    viewer.append(h('div', { class: 'row' }, h('b', { class: 'mono' }, path),
      segmented([['file', 'Whole file'], ['changes', 'Changes this round']], mode, (k) => nav({ view: k })),
      h('span', { class: 'spacer' })));
    const box = h('div', { style: { marginTop: '8px' } }, h('p', { class: 'loading' }, 'Loading…'));
    viewer.append(box);
    (async () => {
      try {
        if (mode === 'changes') {
          const d = await api(`run/${enc(id)}/diff?round=${R.round}&path=${enc(path)}`);
          clear(box);
          if (!d.text) { box.append(h('p', { class: 'muted' }, 'No changes to this file in this round.')); return; }
          const pre = h('pre', { class: 'diff' });
          for (const line of d.text.split('\n')) {
            const cls = line.startsWith('+++') || line.startsWith('---') || line.startsWith('diff ') || line.startsWith('index ') ? 'meta'
              : line.startsWith('+') ? 'add' : line.startsWith('-') ? 'del' : line.startsWith('@@') ? 'hunk' : '';
            pre.append(h('span', { class: cls }, line || ' '));
          }
          box.append(h('div', { class: 'code', style: { display: 'block' } }, pre));
        } else {
          const f = await api(`run/${enc(id)}/file?round=${R.round}&path=${enc(path)}`);
          clear(box);
          if (f.binary) { box.append(h('p', { class: 'muted' }, `Binary file, ${fmt.bytes(f.bytes)}.`)); return; }
          const lines = f.text.split('\n');
          if (lines[lines.length - 1] === '') lines.pop();
          box.append(h('p', { class: 'small muted' }, `${fmt.int(lines.length)} lines · ${fmt.bytes(f.bytes)}${f.cut ? ' · only the first 3 MB shown' : ''}`));
          box.append(h('div', { class: 'code' }, h('pre', { class: 'gutter' }, lines.map((_, i) => i + 1).join('\n')), h('pre', { class: 'src' }, lines.join('\n'))));
        }
      } catch (e) { clear(box); box.append(errorBox(e)); }
    })();
  } else viewer.append(h('p', { class: 'muted' }, 'Pick a file.'));
  el.append(h('div', { class: 'files-layout' }, listCard, viewer));
}

// ---------------------------------------------------------------- tests

async function testsTab(el, env) {
  const { id, params, ctx, S } = env;
  const set = params.get('set') || 'hidden';
  const roundParam = params.get('round');
  const t = await api(`run/${enc(id)}/tests?partition=${set}${roundParam != null ? '&round=' + roundParam : ''}`);
  const matrix = await api(`run/${enc(id)}/matrix?partition=${set}`).catch(() => null);
  const nav = (p) => ctx.go(`/run/${enc(id)}/tests`, Object.fromEntries(Object.entries({ set, round: t.round, ...p }).filter(([, v]) => v != null && v !== '')));
  el.append(h('div', { class: 'row' },
    segmented([['hidden', 'Hidden tests (final score)'], ['visible', 'Visible tests (progress score)']], set, (k) => nav({ set: k, round: null })),
    t.rounds.length ? h('select', { class: 'pick', onchange: (e) => nav({ round: e.target.value }) }, t.rounds.map((r) => h('option', { value: r, selected: r === t.round }, `version after round ${r}`))) : null));
  if (!t.summary) { el.append(h('p', { class: 'muted' }, 'No results for this set of tests.')); return; }
  const sm = t.summary;
  const sql = t.tests.some((x) => x.score != null);
  el.append(h('div', { class: 'kpis' },
    kpi('Score', scoreCell(sm.score, null), `${set === 'hidden' ? 'hidden' : 'visible'} tests, version after round ${t.round}`),
    kpi(sql ? 'Scripts fully passed' : 'Tests passed', `${fmt.int(sm.passed)} of ${fmt.int(sm.total)}`, sql ? `checks passed: ${fmt.int(sm.records_passed)} of ${fmt.int(sm.records_total)}` : null),
    kpi('Build', t.build.ok ? 'built' : 'did not build', t.build.command ? t.build.command.join(' ').slice(0, 60) : null, t.build.ok ? 'good' : 'bad'),
    kpi('Source rules check', t.audit.passed === false ? 'problems found' : 'passed', `${plural((t.audit.findings || []).length, 'finding')}`, t.audit.passed === false ? 'warn' : '')));
  if (t.corrected_by) el.append(h('div', { class: 'notice warn' }, `These results come from the corrected re-score in ${t.corrected_by}, not from the values recorded during the run.`));
  const many = t.tests.length > 60;
  let onlyFailed = many;
  const tableBox = h('div');
  const drawTable = () => {
    clear(tableBox);
    const rows = t.tests.filter((x) => !onlyFailed || !x.passed);
    tableBox.append(table([
      { key: 'id', label: 'Test', render: (x) => h('span', { class: 'mono small' }, String(x.id).replace(/^test\//, '')) },
      { key: 'stage', label: 'Stage', num: true },
      ...(sql ? [] : [{ key: 'validity', label: 'Program', render: (x) => (x.validity === 'invalid' ? 'invalid (should be rejected)' : 'valid') }]),
      { key: 'score', label: sql ? 'Score' : 'Result', num: true, render: (x) => (sql ? h('span', null, scoreBar(x.score), ' ', fmt.score(x.score, x.score > 0 && x.score < 1 ? 4 : 3)) : x.passed ? h('span', { class: 'good' }, 'passed') : h('span', { class: 'bad' }, 'failed')), sort: (x) => (sql ? x.score : x.passed ? 1 : 0) },
      ...(sql ? [{ key: 'checks', label: 'Checks passed', num: true, render: (x) => (x.records ? `${fmt.int(x.records.passed)} / ${fmt.int(x.records.total)}` : '–'), sort: (x) => x.records?.passed }] : []),
      { key: 'failure', label: 'What went wrong', render: (x) => (x.failure ? h('span', { class: 'bad' }, FAILURE[x.failure] || x.failure) : ''), sort: (x) => x.failure || '' },
      { key: 'detail', label: 'Details', cls: 'wrap', nosort: true, render: (x) => detailView(x) },
      { key: 'seconds', label: 'Time', num: true, render: (x) => fmt.dur(x.seconds) },
    ], rows, { sortKey: sql ? 'stage' : 'stage', sortDir: 1 }));
  };
  drawTable();
  el.append(h('section', { class: 'card' }, ...cardHead(`${plural(t.tests.length, 'test')}`, many ? h('label', { class: 'check' }, h('input', { type: 'checkbox', checked: onlyFailed, onchange: (e) => { onlyFailed = e.target.checked; drawTable(); } }), 'only tests that did not pass') : null,
    sql ? 'Each test is one script of SQL statements with expected answers; its score is the share of checks the engine answered exactly as SQLite does.' : 'Each test is one C program: valid ones must compile and behave like GCC’s build; invalid ones must be rejected.'), tableBox));
  if (matrix && matrix.rounds.length > 1) {
    const unsteady = matrix.tests.map((_, i) => matrix.cells[i].some((v) => v == null || v < 1));
    let all = unsteady.filter(Boolean).length === matrix.tests.length || matrix.tests.length <= 30;
    const box = h('div');
    const draw = () => {
      clear(box);
      const idx = matrix.tests.map((_, i) => i).filter((i) => all || unsteady[i]);
      if (!idx.length) { box.append(h('p', { class: 'muted' }, 'Every test passed in every saved version.')); return; }
      box.append(heatmap({
        rows: idx.map((i) => ({ label: String(matrix.tests[i]).replace(/^test\//, '') })), cols: matrix.rounds.map((r) => `r${r}`),
        cells: idx.map((i) => matrix.cells[i]), tiny: idx.length > 40 || matrix.rounds.length > 12,
        title: (i, j, v) => `${matrix.tests[idx[i]]}\nround ${matrix.rounds[j]}: ${v == null ? 'not run' : fmt.score(v)}`,
        onCell: (i, j) => nav({ round: matrix.rounds[j] }),
      }));
    };
    draw();
    const toggle = matrix.tests.length > 30 ? h('label', { class: 'check' }, h('input', { type: 'checkbox', checked: all, onchange: (e) => { all = e.target.checked; draw(); } }), `show all ${matrix.tests.length} tests`) : null;
    el.append(h('section', { class: 'card' }, ...cardHead('Each test across the saved versions', toggle,
      `Rows are tests, columns are the versions saved after each round. Click a cell to look at that version.${toggle ? ' Tests that passed in every version are hidden unless you tick the box.' : ''}`), box));
  }
  if (t.build.output) {
    el.append(h('section', { class: 'card' }, h('h3', null, 'Build output'), h('p', { class: 'explain' }, `${(t.build.command || []).join(' ')} · exit ${t.build.returncode} · ${fmt.dur(t.build.seconds)}${t.build.cut ? ' · last 40,000 characters' : ''}`),
      lazyDetails('show the build output', () => h('pre', { class: 'codebox' }, t.build.output), { open: !t.build.ok })));
  }
  if ((t.audit.findings || []).length) {
    el.append(h('section', { class: 'card' }, h('h3', null, 'Source rules check'), h('pre', { class: 'codebox' }, t.audit.findings.map((f) => (typeof f === 'string' ? f : JSON.stringify(f))).join('\n'))));
  }
  void S;
}

function detailView(x) {
  if (!x.failure) return '';
  const lines = (x.failures || []).map((f) => `line ${f.line}: ${f.detail}`);
  const text = lines.length ? lines.join('\n') : x.detail;
  if (!text) return '';
  if (text.length < 180) return h('span', { class: 'mono small', style: { whiteSpace: 'pre-wrap' } }, text);
  return lazyDetails(text.split('\n')[0].slice(0, 120) + '…', () => h('pre', { class: 'codebox' }, text + (x.detail && lines.length ? '\n\n' + x.detail : '')));
}

// ---------------------------------------------------------------- tools

function toolsTab(el, env) {
  const { id, D, T, data, S, ctx } = env;
  const go = ctx.go;
  const reasoning = data.reasoning || {};
  const perReply = reasoning.status === 'ready' && reasoning.aligned ? reasoning.per_reply : null;
  el.append(h('div', { class: 'kpis' },
    kpi('Tool calls', fmt.int(T.calls), `${fmt.pct(T.failed / (T.calls || 1))} failed`),
    kpi('Shell commands', fmt.int(T.shell.calls), `${fmt.int(T.shell.long)} ran 2 minutes or more`),
    kpi('Blocked by the rule checker', fmt.int(T.blocked), 'commands refused before running'),
    kpi('Files', `${fmt.int(T.files.writes)} writes`, `${fmt.int(T.files.edits)} edits (${fmt.int(T.files.failed_edits)} failed) · ${fmt.int(T.files.reads)} reads`),
    kpi('Replies without a tool call', fmt.int(T.replies - (T.stops.toolUse || 0)), `${fmt.int(T.ended_turn)} ended the turn · ${fmt.int(T.cut_off)} cut off`),
    kpi('Summaries', fmt.int(T.summaries), `${fmt.int(T.summary_written)} tokens written for them`)));

  const tools = Object.entries(T.by_tool).map(([name, v]) => ({ name, ...v }));
  el.append(h('div', { class: 'grid2' },
    h('section', { class: 'card' }, h('h3', null, 'Calls by tool'), table([
      { key: 'name', label: 'Tool', render: (r) => h('span', null, h('span', { class: 'dot', style: { background: toolColor(r.name) } }), r.name) },
      { key: 'calls', label: 'Calls', num: true },
      { key: 'failed', label: 'Failed', num: true, render: (r) => `${r.failed} (${fmt.pct(r.failed / (r.calls || 1))})` },
      { key: 'seconds', label: 'Time spent', num: true, render: (r) => fmt.dur(r.seconds) },
      { key: 'no_result', label: 'No result', num: true, title: 'calls whose result was never saved (round cut off, or reply cut off)' },
    ], tools, { sortKey: 'calls' })),
    h('section', { class: 'card' }, ...cardHead('Why tool calls failed', null, 'Read from the error each failed call returned.'),
      Object.keys(T.why_failed).length ? barChart({
        categories: Object.keys(T.why_failed), format: fmt.int, labelWidth: 230,
        series: [{ name: 'failed calls', color: 'var(--bad)', values: Object.values(T.why_failed) }],
      }) : h('p', { class: 'muted' }, 'No failed calls.'))));

  const kinds = Object.entries(T.shell.by_kind);
  el.append(h('section', { class: 'card' }, ...cardHead('What the shell commands did', null,
    'Each command is put under the first of these it matches: writes files, builds or type-checks, runs tests, runs its own program, probes its own code, reads or searches files, uses git, other. Bars show number of commands; hover for time.'),
    kinds.length ? barChart({
      categories: kinds.map(([k]) => k), format: fmt.int, labelWidth: 180,
      series: [{ name: 'commands', color: toolColor('bash'), values: kinds.map(([, v]) => v.calls) }],
      tooltip: (i) => tipLines(kinds[i][0], [`${fmt.int(kinds[i][1].calls)} commands`, `${fmt.dur(kinds[i][1].seconds)} running`]),
    }) : h('p', { class: 'muted' }, 'No shell commands.')));

  const shell = D.calls.filter((c) => c.name === 'bash' && c.d != null).sort((a, b) => b.d - a.d).slice(0, 15);
  el.append(h('section', { class: 'card' }, h('h3', null, 'Slowest shell commands'), table([
    { key: 'd', label: 'Took', num: true, render: (c) => fmt.dur(c.d) },
    { key: 'r', label: 'Round', num: true },
    { key: 'cmd', label: 'Command', cls: 'wrap', render: (c) => h('span', { class: 'mono small' }, String(c.cmd).slice(0, 400)) },
    { key: 'err', label: 'Result', render: (c) => (c.err ? h('span', { class: 'bad' }, c.why) : 'ok') },
  ], shell, { sortKey: 'd', onRow: (c) => go(`/run/${enc(id)}/conversation`, { round: c.r, k: c.k }) })));

  const failed = D.calls.filter((c) => c.err);
  el.append(h('section', { class: 'card' }, ...cardHead(`Failed tool calls (${failed.length})`, null, 'Click a row to see it in the conversation.'), table([
    { key: 'r', label: 'Round', num: true },
    { key: 't', label: 'When', num: true, render: (c) => fmt.clock(D.t0 + c.t * 1000), sort: (c) => c.t },
    { key: 'name', label: 'Tool' },
    { key: 'why', label: 'Why' },
    { key: 'cmd', label: 'What it tried', cls: 'wrap', render: (c) => h('span', { class: 'mono small' }, String(c.cmd).slice(0, 300)) },
    { key: 'msg', label: 'Error', cls: 'wrap', render: (c) => h('span', { class: 'small' }, c.msg || '') },
  ], failed, { sortKey: 't', sortDir: 1, maxHeight: '520px', onRow: (c) => go(`/run/${enc(id)}/conversation`, { round: c.r, k: c.k }) })));

  if (D.guard.length) {
    el.append(h('section', { class: 'card' }, ...cardHead(`Stopped by the rule checker (${D.guard.length})`, null, 'The harness checks every tool call against the rules of the experiment (no downloads, no existing database engine or compiler, no reading of hidden tests, …) and refuses those that break them. It matches text, so it can also refuse legitimate commands that merely mention a forbidden word.'), table([
      { key: 't', label: 'When', num: true, render: (g) => (g.t != null ? fmt.clock(D.t0 + g.t * 1000) : '–') },
      { key: 'tool', label: 'Tool' },
      { key: 'reason', label: 'Reason', cls: 'wrap' },
      { key: 'what', label: 'Command', cls: 'wrap', render: (g) => h('span', { class: 'mono small' }, g.what) },
    ], D.guard, { sortKey: 't', sortDir: 1, onRow: (g) => { if (g.k != null) { const c = D.calls.find((x) => x.k === g.k); go(`/run/${enc(id)}/conversation`, { round: c ? c.r : 0, k: g.k }); } } })));
  }

  if (D.summaries.length) {
    el.append(h('section', { class: 'card' }, ...cardHead(`Conversation summaries (${D.summaries.length})`, null, 'When the conversation gets close to the model’s limit, the agent program asks the model to summarize it and continues from the summary. The model writes nothing else meanwhile.'), table([
      { key: 'n', label: '#', num: true, render: (x) => D.summaries.indexOf(x) + 1, sort: (x) => x.t },
      { key: 't', label: 'When', num: true, render: (x) => fmt.clock(D.t0 + x.t * 1000) },
      { key: 'r', label: 'Round', num: true },
      { key: 'before', label: 'Conversation before', num: true, render: (x) => fmt.int(x.before) },
      { key: 'written', label: 'Summary tokens written', num: true, render: (x) => fmt.int(x.written) },
      { key: 'd', label: 'Took', num: true, render: (x) => fmt.dur(x.d) },
    ], D.summaries, { sortKey: 't', sortDir: 1, maxHeight: '420px', onRow: (x) => go(`/run/${enc(id)}/conversation`, { round: x.r, k: x.k }) })));
  }

  if (D.unfinished.length) {
    el.append(h('section', { class: 'card' }, ...cardHead(`Replies that did not call a tool (${D.unfinished.length})`, null, 'A reply without a tool call ends the agent’s turn, which ends the round; a reply cut off at the length limit is thrown away.'), table([
      { key: 't', label: 'When', num: true, render: (x) => fmt.clock(D.t0 + x.t * 1000) },
      { key: 'r', label: 'Round', num: true },
      { key: 'stop', label: 'What happened', render: (x) => STOP[x.stop] || x.stop },
      { key: 'out', label: 'Tokens written', num: true, render: (x) => fmt.int(x.out) },
      { key: 'd', label: 'Took', num: true, render: (x) => fmt.dur(x.d) },
      { key: 'head', label: 'It said', cls: 'wrap', render: (x) => h('span', { class: 'small' }, x.head) },
    ], D.unfinished, { sortKey: 't', sortDir: 1, onRow: (x) => go(`/run/${enc(id)}/conversation`, { round: x.r, k: x.k }) })));
  }

  if (perReply) {
    const budget = S.thinking_budget;
    const top = Math.max(...perReply, 1);
    const step = budget ? budget / 8 : Math.ceil(top / 12 / 256) * 256;
    const bins = [];
    for (let v = 0; v <= top; v += step) bins.push(v);
    const counts = bins.map((b, i) => perReply.filter((x) => x >= b && (i === bins.length - 1 || x < bins[i + 1])).length);
    const atLimit = budget ? perReply.filter((x) => Math.abs(x - budget) <= 8).length : null;
    el.append(h('section', { class: 'card' }, ...cardHead('Thinking per reply', null,
      `How many tokens each reply spent thinking before answering (counted with the model’s tokenizer). ${budget ? `${fmt.int(atLimit)} of ${fmt.int(perReply.length)} replies stopped at the thinking limit of ${fmt.int(budget)} tokens.` : ''} Middle reply: ${fmt.int(median(perReply))} tokens.`),
      barChart({
        categories: bins.map((b) => `${fmt.compact(b)}–${fmt.compact(b + step)}`), horizontal: false, height: 200, format: fmt.int,
        series: [{ name: 'replies', color: 'var(--c-thinking)', values: counts }], xLabel: 'thinking tokens in the reply', legend: false,
      })));
  }
}

function median(values) {
  const v = values.filter((x) => x != null).slice().sort((a, b) => a - b);
  if (!v.length) return null;
  const m = Math.floor(v.length / 2);
  return v.length % 2 ? v[m] : (v[m - 1] + v[m]) / 2;
}

// ---------------------------------------------------------------- setup

async function setupTab(el, env) {
  const { id, S } = env;
  const st = await api(`run/${enc(id)}/setup`);
  const cond = st.condition || {};
  const model = st.model || {};
  const sp = model.sampling_params || {};
  const cfg = st.config || {};
  const kv = (pairs) => h('table', { class: 'kv' }, h('tbody', null, pairs.filter(([, v]) => v != null && v !== '').map(([k, v]) => h('tr', null, h('td', null, k), h('td', null, v)))));
  el.append(h('div', { class: 'grid2' },
    h('section', { class: 'card' }, h('h3', null, 'The task and the variant'), kv([
      ['Task', TASK[S.task] || S.task],
      ['Variant', cond.id],
      ['What the variant changes', cond.description],
      ['Language', `${S.language}${S.framework ? ' (' + S.framework + ')' : ''}`],
      ['Test access', cond.tests ? `${cond.tests.access}${cond.tests.feedback && cond.tests.feedback !== 'none' ? ', feedback: ' + cond.tests.feedback : ''}` : null],
      ['Reference implementation', cond.reference ? cond.reference.mode : null],
      ['Specification', cond.specification ? `${cond.specification.path} (${cond.specification.delivery})` : null],
      ['Study', st.study?.id ? `${st.study.id} (${st.study.path})` : null],
      ['Kind of run', PROFILE[S.profile] || S.profile],
    ])),
    h('section', { class: 'card' }, h('h3', null, 'The model and its server'), kv([
      ['Model', model.id],
      ['Server', S.server],
      ['Thinking level', model.thinking],
      ['Conversation limit (context window)', model.context_window ? fmt.int(model.context_window) + ' tokens' : null],
      ['Reply length limit', model.max_tokens ? fmt.int(model.max_tokens) + ' tokens' : null],
      ['Thinking limit per reply', S.thinking_budget ? fmt.int(S.thinking_budget) + ' tokens' : 'none'],
      ['Sampling', Object.entries(sp).filter(([k]) => k !== 'custom_params').map(([k, v]) => `${k} ${v}`).join(', ')],
      ['Endpoint', model.base_url],
    ]))));
  const b = st.budget || {};
  el.append(h('div', { class: 'grid2' },
    h('section', { class: 'card' }, h('h3', null, 'Budget'), kv([
      ['Time', b.wall_hours != null ? `${b.wall_hours} h` : null],
      ['Rounds at most', b.max_rounds],
      ['Time limit per round', b.round_timeout_minutes != null ? `${b.round_timeout_minutes} min` : null],
      ['Stages scored', b.max_stage],
    ])),
    h('section', { class: 'card' }, h('h3', null, 'The agent'), kv([
      ['Agent program', cfg.PI_VERSION ? `Pi ${cfg.PI_VERSION}` : null],
      ['Tools it had', cfg.PI_TOOLS],
      ['Shell command time limit', cfg.BASH_TIMEOUT_PACKAGE ? `${cfg.BASH_TIMEOUT_PACKAGE} ${cfg.BASH_TIMEOUT_PACKAGE_VERSION || ''} (default 120 s)` : null],
      ['Harness add-ons', (st.extensions || []).join(', ')],
      ['Container image', st.image ? `${st.image.name} (${String(st.image.id || '').slice(7, 19)})` : null],
      ['Agent container limits', cfg.AGENT_CPUS ? `${cfg.AGENT_CPUS} CPUs, ${cfg.AGENT_MEMORY} memory` : null],
    ]))));
  if (st.pi_settings) el.append(h('section', { class: 'card' }, h('h3', null, 'Agent settings (Pi settings.json)'), h('pre', { class: 'codebox' }, JSON.stringify(st.pi_settings, null, 2))));
  const prompts = h('section', { class: 'card' }, h('h3', null, 'What the agent was given'), h('p', { class: 'explain' }, 'The files and prompts as they were frozen for this run. Empty files are one byte or less.'));
  for (const p of st.prompts || []) {
    prompts.append(lazyDetails(`${p.name} — ${plural(p.bytes, 'byte')}`, () => {
      const box = h('div', null, h('p', { class: 'loading' }, 'Loading…'));
      api(`run/${enc(id)}/prompt?name=${enc(p.name)}`).then((x) => box.replaceChildren(h('pre', { class: 'codebox' }, x.text || '(empty)'))).catch((e) => box.replaceChildren(errorBox(e)));
      return box;
    }));
  }
  el.append(prompts);
  if ((st.attempts || []).length) {
    el.append(h('section', { class: 'card' }, h('h3', null, 'Executions'), table([
      { key: 'index', label: '#', num: true },
      { key: 'kind', label: 'Kind' },
      { key: 'started_at', label: 'Started', render: (a) => fmt.when(a.started_at) },
      { key: 'ended_at', label: 'Ended', render: (a) => fmt.when(a.ended_at) },
      { key: 'rounds', label: 'Rounds', render: (a) => `${a.first_round}–${a.last_round}` },
      { key: 'status', label: 'Status', render: (a) => `${a.status}${a.termination_reason ? ' · ' + (END[a.termination_reason] || a.termination_reason) : ''}` },
    ], st.attempts, { sortKey: 'index', sortDir: 1 })));
  }
  if (st.report) {
    el.append(h('section', { class: 'card' }, h('h3', null, 'Run report written by the harness'), lazyDetails('show report.md', () => {
      const box = h('div', { class: 'doc' }, h('p', { class: 'loading' }, 'Loading…'));
      api(`run/${enc(id)}/prompt?name=report.md`).then((x) => { box.innerHTML = renderMarkdown(x.text, `runs/${id}/report.md`); }).catch((e) => box.replaceChildren(errorBox(e)));
      return box;
    })));
  }
  el.append(h('section', { class: 'card' }, h('h3', null, 'Every recorded setting'), h('p', { class: 'explain' }, 'The configuration frozen for this run (secret settings are left out).'),
    lazyDetails(`${Object.keys(cfg).length} settings`, () => kv(Object.entries(cfg).map(([k, v]) => [k, h('span', { class: 'mono small' }, String(v))])))));
  if (st.adapter) el.append(h('section', { class: 'card' }, h('h3', null, 'How the product is built and run (adapter)'), lazyDetails('show candidate.json', () => h('pre', { class: 'codebox' }, JSON.stringify(st.adapter, null, 2)))));
}
