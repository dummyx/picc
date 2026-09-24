// Small SVG charts drawn at the container's real width, with hover details and clicks.

import { h, s, clear, fmt, showTip, hideTip, heatColor } from './util.js';

// Draws with the element's actual width and redraws when that changes.
function responsive(height, draw, cls = '') {
  const box = h('div', { class: 'chart ' + cls });
  let lastW = 0;
  const redraw = () => {
    const w = Math.floor(box.clientWidth);
    if (!w || Math.abs(w - lastW) < 2) return;
    lastW = w;
    clear(box);
    draw(box, w, typeof height === 'function' ? height(w) : height);
  };
  const ro = new ResizeObserver(() => requestAnimationFrame(redraw));
  ro.observe(box);
  box.redraw = () => { lastW = 0; redraw(); };
  return box;
}

export function niceTicks(min, max, count = 5) {
  if (!Number.isFinite(min) || !Number.isFinite(max)) return [0, 1];
  if (max === min) max = min + 1;
  const raw = (max - min) / count;
  const mag = Math.pow(10, Math.floor(Math.log10(raw)));
  const step = [1, 2, 2.5, 5, 10].map((m) => m * mag).find((st) => st >= raw) || 10 * mag;
  const out = [];
  for (let v = Math.ceil(min / step - 1e-9) * step; v <= max + step * 1e-6; v += step) out.push(+v.toFixed(10));
  return out;
}

// Ticks whose last value is at or above `max`, so nothing drawn runs past the axis.
export function niceScale(min, max, count = 5) {
  const ticks = niceTicks(min, max, count);
  const step = ticks.length > 1 ? ticks[1] - ticks[0] : (max - min || 1);
  while (ticks[ticks.length - 1] < max - 1e-9) ticks.push(+(ticks[ticks.length - 1] + step).toFixed(10));
  return ticks;
}

export const scoreAxis = (label) => ({ min: 0, max: 1, ticks: [0, 0.2, 0.4, 0.6, 0.8, 1], format: (v) => v.toFixed(1), label });

export function timeTicks(max, count = 7) {
  const steps = [15, 30, 60, 120, 300, 600, 900, 1800, 3600, 7200, 10800, 21600, 43200, 86400];
  const step = steps.find((st) => max / st <= count) || 86400;
  const out = [];
  for (let v = 0; v <= max + 1e-6; v += step) out.push(v);
  return out;
}

export function timeLabel(sec) {
  if (sec < 60) return Math.round(sec) + 's';
  if (sec < 3600) return Math.round(sec / 60) + 'm';
  const hh = Math.floor(sec / 3600), mm = Math.round((sec % 3600) / 60);
  return mm ? `${hh}h${String(mm).padStart(2, '0')}` : `${hh}h`;
}

function legendRow(items, onToggle) {
  const row = h('div', { class: 'legend' });
  for (const it of items) {
    const el = h('span', { class: 'item' + (onToggle ? ' toggle' : '') + (it.off ? ' off' : '') },
      h('span', { class: it.shape === 'line' ? 'line' : 'swatch', style: { background: it.color } }), it.name);
    if (onToggle) el.addEventListener('click', () => onToggle(it));
    row.append(el);
  }
  return row;
}

// ---------------------------------------------------------------- line chart

export function lineChart(opts) {
  const {
    series, height = 260, x = {}, y = {}, markers = [], hlines = [], onClick, tooltip, legend = true,
    dots = 'auto', hover = 'nearest',
  } = opts;
  const hidden = new Set();
  const wrap = h('div');
  const chart = responsive(height, (box, W, H) => {
    const shown = series.filter((sr) => !hidden.has(sr.name));
    const pts = shown.flatMap((sr) => sr.points.filter((p) => p.y != null && p.x != null));
    const pad = { l: y.width || 50, r: 14, t: 10, b: x.label ? 38 : 26 };
    let xmin = x.min ?? Math.min(...pts.map((p) => p.x), ...markers.map((m) => m.x));
    let xmax = x.max ?? Math.max(...pts.map((p) => p.x), ...markers.map((m) => m.x));
    if (!Number.isFinite(xmin)) { xmin = 0; xmax = 1; }
    if (xmax <= xmin) xmax = xmin + 1;
    let ymin = y.min ?? Math.min(0, ...pts.map((p) => p.y));
    let ymax = y.max ?? Math.max(...pts.map((p) => p.y), ...hlines.filter((l) => l.fit).map((l) => l.y));
    if (!Number.isFinite(ymax)) ymax = 1;
    if (ymax <= ymin) ymax = ymin + 1;
    const iw = W - pad.l - pad.r, ih = H - pad.t - pad.b;
    let autoTicks = null;
    if (y.max == null && !y.ticks) {
      autoTicks = niceScale(ymin, ymax, Math.max(2, Math.floor(ih / 46)));
      ymax = autoTicks[autoTicks.length - 1];
    }
    const X = (v) => pad.l + ((v - xmin) / (xmax - xmin)) * iw;
    const Y = (v) => pad.t + ih - ((v - ymin) / (ymax - ymin)) * ih;
    const svg = s('svg', { width: W, height: H, viewBox: `0 0 ${W} ${H}` });
    const yt = y.ticks || autoTicks || niceTicks(ymin, ymax, Math.max(2, Math.floor(ih / 46)));
    for (const v of yt) {
      if (v < ymin - 1e-9 || v > ymax + 1e-9) continue;
      svg.append(s('line', { class: 'gridline', x1: pad.l, x2: W - pad.r, y1: Y(v), y2: Y(v) }));
      svg.append(s('text', { x: pad.l - 6, y: Y(v) + 3.5, 'text-anchor': 'end' }, (y.format || fmt.compact)(v)));
    }
    const xt = x.time ? timeTicks(xmax, Math.max(3, Math.floor(iw / 80))) : (x.ticks || niceTicks(xmin, xmax, Math.max(3, Math.floor(iw / 90))));
    for (const v of xt) {
      if (v < xmin - 1e-9 || v > xmax + 1e-9) continue;
      svg.append(s('line', { class: 'axisline', x1: X(v), x2: X(v), y1: pad.t + ih, y2: pad.t + ih + 4 }));
      svg.append(s('text', { x: X(v), y: pad.t + ih + 16, 'text-anchor': 'middle' }, (x.format || (x.time ? timeLabel : fmt.compact))(v)));
    }
    svg.append(s('line', { class: 'axisline', x1: pad.l, x2: W - pad.r, y1: pad.t + ih, y2: pad.t + ih }));
    if (x.label) svg.append(s('text', { class: 'axislabel', x: pad.l + iw / 2, y: H - 4, 'text-anchor': 'middle' }, x.label));
    if (y.label) svg.append(s('text', { class: 'axislabel', x: 12, y: pad.t + ih / 2, transform: `rotate(-90 12 ${pad.t + ih / 2})`, 'text-anchor': 'middle' }, y.label));
    for (const m of markers) {
      if (m.x < xmin || m.x > xmax) continue;
      svg.append(s('line', { x1: X(m.x), x2: X(m.x), y1: pad.t, y2: pad.t + ih, stroke: m.color || 'var(--c-summaries)', 'stroke-width': 1, 'stroke-dasharray': '3 3', opacity: 0.55 }));
    }
    for (const l of hlines) {
      if (l.y < ymin || l.y > ymax) continue;
      svg.append(s('line', { x1: pad.l, x2: W - pad.r, y1: Y(l.y), y2: Y(l.y), stroke: l.color || 'var(--bad)', 'stroke-width': 1.2, 'stroke-dasharray': '5 4', opacity: 0.8 }));
      if (l.label) svg.append(s('text', { x: W - pad.r - 4, y: Y(l.y) - 4, 'text-anchor': 'end', style: `fill:${l.color || 'var(--bad)'}` }, l.label));
    }
    const drawDots = dots === true || (dots === 'auto' && pts.length <= 260);
    const pix = [];
    for (const sr of shown) {
      const ps = sr.points.filter((p) => p.y != null && p.x != null);
      if (!ps.length) continue;
      if (sr.bars) {
        const bw = Math.max(1, Math.min(8, iw / Math.max(ps.length, 1) * 0.8));
        for (const p of ps) {
          svg.append(s('rect', { x: X(p.x) - bw / 2, y: Math.min(Y(p.y), Y(0)), width: bw, height: Math.abs(Y(0) - Y(p.y)), fill: p.color || sr.color, opacity: 0.85 }));
          pix.push({ px: X(p.x), py: Y(p.y), p, sr });
        }
        continue;
      }
      if (!sr.noLine && ps.length > 1) {
        let d = '';
        ps.forEach((p, i) => {
          if (sr.step && i > 0) d += `L${X(p.x).toFixed(1)},${Y(ps[i - 1].y).toFixed(1)}`;
          d += `${i ? 'L' : 'M'}${X(p.x).toFixed(1)},${Y(p.y).toFixed(1)}`;
        });
        svg.append(s('path', { d, fill: 'none', stroke: sr.color, 'stroke-width': sr.width || 2, 'stroke-dasharray': sr.dash || null, 'stroke-linejoin': 'round', opacity: sr.opacity || 1 }));
      }
      for (const p of ps) {
        const px = X(p.x), py = Y(p.y);
        pix.push({ px, py, p, sr });
        if (drawDots || sr.noLine || p.mark) {
          svg.append(s('circle', { cx: px, cy: py, r: p.mark ? 4.5 : (sr.r || 3), fill: p.hollow ? 'var(--panel)' : (p.color || sr.color), stroke: p.color || sr.color, 'stroke-width': p.hollow ? 2 : 0 }));
        }
      }
    }
    const hoverDot = s('circle', { class: 'hover-dot', r: 6, fill: 'none', stroke: 'var(--text)', 'stroke-width': 1.5, visibility: 'hidden' });
    svg.append(hoverDot);
    const overlay = s('rect', { x: pad.l, y: pad.t, width: iw, height: ih, fill: 'transparent', class: onClick ? 'clicky' : '' });
    svg.append(overlay);
    let current = null;
    const find = (ev) => {
      const r = svg.getBoundingClientRect();
      const mx = ev.clientX - r.left, my = ev.clientY - r.top;
      let best = null, bd = Infinity;
      for (const q of pix) {
        const d = hover === 'x' ? Math.abs(q.px - mx) : (q.px - mx) ** 2 + (q.py - my) ** 2;
        if (d < bd) { bd = d; best = q; }
      }
      return best;
    };
    overlay.addEventListener('mousemove', (ev) => {
      current = find(ev);
      if (!current) return;
      hoverDot.setAttribute('cx', current.px);
      hoverDot.setAttribute('cy', current.py);
      hoverDot.setAttribute('visibility', 'visible');
      const content = tooltip ? tooltip(current.p, current.sr) : `${current.sr.name}: ${(y.format || fmt.compact)(current.p.y)}`;
      if (content) showTip(ev, content);
    });
    overlay.addEventListener('mouseleave', () => { hoverDot.setAttribute('visibility', 'hidden'); hideTip(); });
    if (onClick) overlay.addEventListener('click', (ev) => { const q = find(ev); if (q) { hideTip(); onClick(q.p, q.sr); } });
    box.append(svg);
  });
  wrap.append(chart);
  if (legend && series.length > 1) {
    const items = series.filter((sr) => !sr.noLegend).map((sr) => ({ name: sr.name, color: sr.color, shape: 'line', off: hidden.has(sr.name) }));
    const seen = new Set();
    const uniq = items.filter((it) => (seen.has(it.name) ? false : seen.add(it.name)));
    const redrawLegend = () => {
      const fresh = legendRow(uniq.map((it) => ({ ...it, off: hidden.has(it.name) })), toggle);
      wrap.replaceChild(fresh, wrap.lastChild);
    };
    const toggle = (it) => { if (hidden.has(it.name)) hidden.delete(it.name); else hidden.add(it.name); chart.redraw(); redrawLegend(); };
    wrap.append(legendRow(uniq, opts.toggle === false ? null : toggle));
  }
  return wrap;
}

// ---------------------------------------------------------------- bar chart (stacked)

export function barChart(opts) {
  const {
    categories, series, horizontal = true, format = fmt.compact, onClick, tooltip, legend = true,
    max, labelWidth = 170, barHeight = 18, height = 240, totals = true, catLabel,
  } = opts;
  const n = categories.length;
  const H0 = horizontal ? n * (barHeight + 8) + 30 : height;
  const wrap = h('div');
  const chart = responsive(H0, (box, W, H) => {
    const svg = s('svg', { width: W, height: H, viewBox: `0 0 ${W} ${H}` });
    const totalsArr = categories.map((_, i) => series.reduce((a, sr) => a + Math.max(0, sr.values[i] || 0), 0));
    const top = max ?? Math.max(...totalsArr, 1e-9);
    const want = horizontal ? Math.max(2, Math.floor((W - labelWidth - 60) / 110)) : 4;
    let ticks = opts.time ? timeTicks(top, want) : niceScale(0, top, want);
    if (opts.time && ticks[ticks.length - 1] < top) ticks.push(ticks[ticks.length - 1] + (ticks[1] - ticks[0] || top));
    const vmax = max ?? ticks[ticks.length - 1];
    const tickText = opts.time ? timeLabel : format;
    if (horizontal) {
      const pad = { l: labelWidth, r: 60, t: 4, b: 22 };
      const iw = W - pad.l - pad.r;
      const X = (v) => pad.l + (v / vmax) * iw;
      for (const t of ticks) {
        if (t > vmax + 1e-9) continue;
        svg.append(s('line', { class: 'gridline', x1: X(t), x2: X(t), y1: pad.t, y2: H - pad.b }));
        svg.append(s('text', { x: X(t), y: H - 6, 'text-anchor': 'middle' }, tickText(t)));
      }
      categories.forEach((cat, i) => {
        const y0 = pad.t + i * (barHeight + 8) + 4;
        const label = typeof cat === 'object' ? cat.label : cat;
        const t = s('text', { x: pad.l - 8, y: y0 + barHeight / 2 + 4, 'text-anchor': 'end', class: catLabel ? 'clicky' : '' }, truncate(label, Math.floor(labelWidth / 6.6)));
        if (typeof cat === 'object' && cat.title) t.append(s('title', null, cat.title));
        if (catLabel) t.addEventListener('click', () => catLabel(i));
        svg.append(t);
        let acc = 0;
        series.forEach((sr, j) => {
          const v = Math.max(0, sr.values[i] || 0);
          if (!v) return;
          const rect = s('rect', { x: X(acc), y: y0, width: Math.max(0.5, X(acc + v) - X(acc)), height: barHeight, fill: sr.color, class: onClick ? 'clicky' : '' });
          rect.addEventListener('mousemove', (ev) => showTip(ev, tooltip ? tooltip(i, j) : `${label}\n${sr.name}: ${format(v)}`));
          rect.addEventListener('mouseleave', hideTip);
          if (onClick) rect.addEventListener('click', () => onClick(i, j));
          svg.append(rect);
          acc += v;
        });
        if (totals) svg.append(s('text', { x: X(acc) + 5, y: y0 + barHeight / 2 + 4 }, format(totalsArr[i])));
      });
    } else {
      const pad = { l: 50, r: 10, t: 10, b: opts.xLabel ? 44 : 30 };
      const iw = W - pad.l - pad.r, ih = H - pad.t - pad.b;
      const Y = (v) => pad.t + ih - (v / vmax) * ih;
      const bw = iw / n;
      for (const t of ticks) {
        svg.append(s('line', { class: 'gridline', x1: pad.l, x2: W - pad.r, y1: Y(t), y2: Y(t) }));
        svg.append(s('text', { x: pad.l - 6, y: Y(t) + 3.5, 'text-anchor': 'end' }, tickText(t)));
      }
      const every = Math.max(1, Math.ceil(n / Math.max(1, Math.floor(iw / 44))));
      categories.forEach((cat, i) => {
        const x0 = pad.l + i * bw + bw * 0.12;
        const w = bw * 0.76;
        let acc = 0;
        series.forEach((sr, j) => {
          const v = Math.max(0, sr.values[i] || 0);
          if (!v) return;
          const rect = s('rect', { x: x0, y: Y(acc + v), width: Math.max(0.5, w), height: Math.max(0.5, Y(acc) - Y(acc + v)), fill: sr.color, class: onClick ? 'clicky' : '' });
          const label = typeof cat === 'object' ? cat.label : cat;
          rect.addEventListener('mousemove', (ev) => showTip(ev, tooltip ? tooltip(i, j) : `${label}\n${sr.name}: ${format(v)}`));
          rect.addEventListener('mouseleave', hideTip);
          if (onClick) rect.addEventListener('click', () => onClick(i, j));
          svg.append(rect);
          acc += v;
        });
        if (i % every === 0) {
          const label = typeof cat === 'object' ? cat.label : cat;
          svg.append(s('text', { x: x0 + w / 2, y: pad.t + ih + 15, 'text-anchor': 'middle' }, truncate(String(label), 12)));
        }
      });
      svg.append(s('line', { class: 'axisline', x1: pad.l, x2: W - pad.r, y1: pad.t + ih, y2: pad.t + ih }));
      if (opts.xLabel) svg.append(s('text', { class: 'axislabel', x: pad.l + iw / 2, y: H - 4, 'text-anchor': 'middle' }, opts.xLabel));
    }
    box.append(svg);
  });
  wrap.append(chart);
  if (legend && series.length > 1) wrap.append(legendRow(series.map((sr) => ({ name: sr.name, color: sr.color }))));
  return wrap;
}

function truncate(text, n) {
  text = String(text);
  return text.length > n ? text.slice(0, Math.max(1, n - 1)) + '…' : text;
}

// ---------------------------------------------------------------- dot plot

export function dotPlot(opts) {
  const { groups, y = {}, height = 250, onClick, tooltip, medians = true } = opts;
  return responsive(height, (box, W, H) => {
    const pad = { l: 46, r: 10, t: 10, b: 30 };
    const iw = W - pad.l - pad.r, ih = H - pad.t - pad.b;
    const ymin = y.min ?? 0, ymax = y.max ?? 1;
    const Y = (v) => pad.t + ih - ((v - ymin) / (ymax - ymin)) * ih;
    const svg = s('svg', { width: W, height: H, viewBox: `0 0 ${W} ${H}` });
    for (const t of niceTicks(ymin, ymax, 5)) {
      svg.append(s('line', { class: 'gridline', x1: pad.l, x2: W - pad.r, y1: Y(t), y2: Y(t) }));
      svg.append(s('text', { x: pad.l - 6, y: Y(t) + 3.5, 'text-anchor': 'end' }, (y.format || fmt.score)(t)));
    }
    const bw = iw / Math.max(groups.length, 1);
    groups.forEach((g, gi) => {
      const cx = pad.l + bw * gi + bw / 2;
      svg.append(s('text', { x: cx, y: H - 10, 'text-anchor': 'middle' }, truncate(g.name, Math.max(6, Math.floor(bw / 6.5)))));
      const vals = g.points.filter((p) => p.y != null).map((p) => p.y).sort((a, b) => a - b);
      if (medians && vals.length > 1) {
        const m = vals.length % 2 ? vals[(vals.length - 1) / 2] : (vals[vals.length / 2 - 1] + vals[vals.length / 2]) / 2;
        const line = s('line', { x1: cx - Math.min(34, bw * 0.35), x2: cx + Math.min(34, bw * 0.35), y1: Y(m), y2: Y(m), stroke: g.color, 'stroke-width': 3, opacity: 0.45, 'stroke-linecap': 'round' });
        line.addEventListener('mousemove', (ev) => showTip(ev, `${g.name}: middle of ${vals.length} runs = ${(y.format || fmt.score)(m)}`));
        line.addEventListener('mouseleave', hideTip);
        svg.append(line);
      }
      const n = g.points.length;
      g.points.forEach((p, i) => {
        if (p.y == null) return;
        const off = n > 1 ? (i - (n - 1) / 2) * Math.min(14, (bw * 0.5) / n) : 0;
        const c = s('circle', { cx: cx + off, cy: Y(p.y), r: 6, fill: p.hollow ? 'var(--panel)' : g.color, stroke: g.color, 'stroke-width': 2, class: onClick ? 'clicky' : '' });
        c.addEventListener('mousemove', (ev) => showTip(ev, tooltip ? tooltip(p, g) : `${p.label}: ${(y.format || fmt.score)(p.y)}`));
        c.addEventListener('mouseleave', hideTip);
        if (onClick) c.addEventListener('click', () => { hideTip(); onClick(p, g); });
        svg.append(c);
        if (p.tag) svg.append(s('text', { x: cx + off + 9, y: Y(p.y) + 4, style: 'font-size:10.5px' }, p.tag));
      });
    });
    svg.append(s('line', { class: 'axisline', x1: pad.l, x2: W - pad.r, y1: pad.t + ih, y2: pad.t + ih }));
    if (y.label) svg.append(s('text', { class: 'axislabel', x: 12, y: pad.t + ih / 2, transform: `rotate(-90 12 ${pad.t + ih / 2})`, 'text-anchor': 'middle' }, y.label));
    box.append(svg);
  });
}

// ---------------------------------------------------------------- activity lanes

export function timeline(opts) {
  const { lanes, segments, colors, onClick, tooltip, laneHeight = 20, labelWidth = 74 } = opts;
  const H0 = lanes.length * (laneHeight + 6) + 30;
  return responsive(H0, (box, W, H) => {
    const pad = { l: labelWidth, r: 12, t: 4, b: 22 };
    const iw = W - pad.l - pad.r;
    const span = Math.max(...lanes.map((l) => l.end - l.start), 1);
    const X = (v) => pad.l + (v / span) * iw;
    const svg = s('svg', { width: W, height: H, viewBox: `0 0 ${W} ${H}` });
    for (const t of timeTicks(span, Math.max(3, Math.floor(iw / 70)))) {
      svg.append(s('line', { class: 'gridline', x1: X(t), x2: X(t), y1: pad.t, y2: H - pad.b }));
      svg.append(s('text', { x: X(t), y: H - 6, 'text-anchor': 'middle' }, timeLabel(t)));
    }
    lanes.forEach((lane, i) => {
      const y0 = pad.t + i * (laneHeight + 6) + 2;
      svg.append(s('text', { x: pad.l - 8, y: y0 + laneHeight / 2 + 4, 'text-anchor': 'end' }, lane.label));
      svg.append(s('rect', { x: X(0), y: y0, width: X(lane.end - lane.start) - X(0), height: laneHeight, fill: 'var(--grid)', rx: 2 }));
    });
    for (const seg of segments) {
      const lane = lanes[seg.lane];
      if (!lane) continue;
      const y0 = pad.t + seg.lane * (laneHeight + 6) + 2;
      const a = Math.max(0, seg.start - lane.start), b = Math.max(a, seg.end - lane.start);
      const rect = s('rect', { x: X(a), y: y0, width: Math.max(0.6, X(b) - X(a)), height: laneHeight, fill: colors[seg.kind] || 'gray', class: onClick && seg.k != null ? 'clicky' : '' });
      rect.addEventListener('mousemove', (ev) => showTip(ev, tooltip ? tooltip(seg) : seg.kind));
      rect.addEventListener('mouseleave', hideTip);
      if (onClick && seg.k != null) rect.addEventListener('click', () => { hideTip(); onClick(seg); });
      svg.append(rect);
    }
    box.append(svg);
  });
}

// ---------------------------------------------------------------- heat map (HTML table)

export function heatmap(opts) {
  const { rows, cols, cells, format = (v) => fmt.score(v, 2), tiny = false, title, colTitles, corner = '' } = opts;
  const table = h('table', { class: 'heat' + (tiny ? ' tiny' : '') });
  const head = h('tr', null, h('th', null, corner));
  cols.forEach((c, j) => head.append(h('th', { class: tiny || cols.length > 10 ? 'col' : '', title: colTitles ? colTitles[j] : c }, c)));
  table.append(h('thead', null, head));
  const body = h('tbody');
  rows.forEach((row, i) => {
    const th = h('th', null, row.label);
    const tr = h('tr', { class: row.onClick ? 'clickable' : '' }, th);
    if (row.onClick) th.addEventListener('click', row.onClick);
    cols.forEach((_, j) => {
      const v = cells[i][j];
      const td = h('td', { class: v == null ? 'empty' : '', style: { background: heatColor(v) } }, v == null ? '·' : format(v));
      const t = title ? title(i, j, v) : null;
      if (t) {
        td.addEventListener('mousemove', (ev) => showTip(ev, t));
        td.addEventListener('mouseleave', hideTip);
      }
      if (opts.onCell) { td.style.cursor = 'pointer'; td.addEventListener('click', () => opts.onCell(i, j)); }
      tr.append(td);
    });
    body.append(tr);
  });
  table.append(body);
  return h('div', { style: { overflowX: 'auto' } }, table);
}

// ---------------------------------------------------------------- tiny dot strip for batch cards

export function dotStrip({ groups, height = 64, onClick }) {
  return responsive(height, (box, W, H) => {
    const pad = { l: 26, r: 6, t: 6, b: 6 };
    const iw = W - pad.l - pad.r, ih = H - pad.t - pad.b;
    const Y = (v) => pad.t + ih - v * ih;
    const svg = s('svg', { width: W, height: H, viewBox: `0 0 ${W} ${H}` });
    for (const t of [0, 0.5, 1]) {
      svg.append(s('line', { class: 'gridline', x1: pad.l, x2: W - pad.r, y1: Y(t), y2: Y(t) }));
      svg.append(s('text', { x: pad.l - 4, y: Y(t) + 3.5, 'text-anchor': 'end', style: 'font-size:9.5px' }, t === 0.5 ? '.5' : String(t)));
    }
    const bw = iw / Math.max(groups.length, 1);
    groups.forEach((g, gi) => {
      const cx = pad.l + bw * gi + bw / 2;
      const n = g.points.length;
      g.points.forEach((p, i) => {
        if (p.y == null) return;
        const off = n > 1 ? (i - (n - 1) / 2) * Math.min(8, (bw * 0.6) / n) : 0;
        const c = s('circle', { cx: cx + off, cy: Y(Math.max(0, Math.min(1, p.y))), r: 3.6, fill: p.hollow ? 'var(--panel)' : g.color, stroke: g.color, 'stroke-width': 1.5, class: 'clicky' });
        c.addEventListener('mousemove', (ev) => showTip(ev, p.label));
        c.addEventListener('mouseleave', hideTip);
        if (onClick) c.addEventListener('click', () => { hideTip(); onClick(p); });
        svg.append(c);
      });
    });
    box.append(svg);
  });
}

export { legendRow };
