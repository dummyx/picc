// A small, safe Markdown renderer for the project's write-ups: everything is
// escaped first and only known tags are produced. Links to other .md files in
// the repository open inside the dashboard.

const esc = (t) => t.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');

function resolve(base, href) {
  if (/^[a-z]+:/i.test(href) || href.startsWith('#') || href.startsWith('/')) return href;
  const parts = base.split('/').slice(0, -1);
  for (const seg of href.split('/')) {
    if (seg === '..') parts.pop();
    else if (seg !== '.') parts.push(seg);
  }
  return parts.join('/');
}

function linkTarget(href, base) {
  href = href.trim();
  if (/^(https?:|mailto:)/i.test(href)) return { url: href, external: true };
  if (href.startsWith('#')) return { url: '#/doc/' + base + href.replace(/^#/, '?at='), external: false };
  const [path, anchor] = href.split('#');
  const full = resolve(base, path);
  if (full.endsWith('.md')) return { url: '#/doc/' + full + (anchor ? '?at=' + anchor : ''), external: false };
  return null;
}

function inline(text, base) {
  const codes = [];
  let out = text.replace(/`([^`]+)`/g, (_, c) => { codes.push(c); return `\u0000${codes.length - 1}\u0000`; });
  out = esc(out);
  out = out.replace(/\[([^\]]+)\]\(([^)\s]+)(?:\s+&quot;[^&]*&quot;)?\)/g, (m, label, href) => {
    const t = linkTarget(href.replace(/&amp;/g, '&'), base);
    if (!t) return label;
    return `<a href="${esc(t.url)}"${t.external ? ' target="_blank" rel="noopener noreferrer"' : ''}>${label}</a>`;
  });
  out = out.replace(/&lt;(https?:\/\/[^\s&]+)&gt;/g, (m, u) => `<a href="${u}" target="_blank" rel="noopener noreferrer">${u}</a>`);
  out = out.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>').replace(/__([^_]+)__/g, '<strong>$1</strong>');
  out = out.replace(/(^|[^*\w])\*([^*\s][^*]*?)\*(?!\w)/g, '$1<em>$2</em>').replace(/(^|[^_\w])_([^_\s][^_]*?)_(?!\w)/g, '$1<em>$2</em>');
  out = out.replace(/~~([^~]+)~~/g, '<del>$1</del>');
  out = out.replace(/\u0000(\d+)\u0000/g, (_, i) => `<code>${esc(codes[+i])}</code>`);
  return out;
}

function slug(text) {
  return text.toLowerCase().replace(/<[^>]+>/g, '').replace(/[^\w\s-]/g, '').trim().replace(/\s+/g, '-');
}

export function renderMarkdown(src, base = '') {
  const lines = src.replace(/\r\n?/g, '\n').split('\n');
  const html = [];
  let i = 0;
  if (lines[0] === '---') {  // front matter
    const end = lines.indexOf('---', 1);
    if (end > 0) {
      html.push(`<pre><code>${esc(lines.slice(1, end).join('\n'))}</code></pre>`);
      i = end + 1;
    }
  }
  const para = [];
  const flush = () => { if (para.length) { html.push(`<p>${inline(para.join(' '), base)}</p>`); para.length = 0; } };
  while (i < lines.length) {
    const line = lines[i];
    const fence = line.match(/^(\s*)(```|~~~)(.*)$/);
    if (fence) {
      flush();
      const body = [];
      i++;
      while (i < lines.length && !lines[i].trim().startsWith(fence[2])) body.push(lines[i++]);
      i++;
      html.push(`<pre><code>${esc(body.join('\n'))}</code></pre>`);
      continue;
    }
    const heading = line.match(/^(#{1,6})\s+(.*?)\s*#*\s*$/);
    if (heading) {
      flush();
      const n = heading[1].length;
      const content = inline(heading[2], base);
      html.push(`<h${n} id="${esc(slug(heading[2]))}">${content}</h${n}>`);
      i++;
      continue;
    }
    if (/^\s*([-*_])\s*(\1\s*){2,}$/.test(line)) { flush(); html.push('<hr>'); i++; continue; }
    if (/^\s*\|.*\|\s*$/.test(line) && i + 1 < lines.length && /^\s*\|?[\s:|-]+\|?\s*$/.test(lines[i + 1]) && lines[i + 1].includes('-')) {
      flush();
      const cells = (row) => row.trim().replace(/^\||\|$/g, '').split(/(?<!\\)\|/).map((c) => c.trim().replace(/\\\|/g, '|'));
      const align = cells(lines[i + 1]).map((c) => (/^:-+:$/.test(c) ? 'center' : /-+:$/.test(c) ? 'right' : ''));
      const head = cells(line);
      let t = '<table><thead><tr>' + head.map((c, j) => `<th${align[j] ? ` style="text-align:${align[j]}"` : ''}>${inline(c, base)}</th>`).join('') + '</tr></thead><tbody>';
      i += 2;
      while (i < lines.length && /^\s*\|.*\|\s*$/.test(lines[i])) {
        t += '<tr>' + cells(lines[i]).map((c, j) => `<td${align[j] ? ` style="text-align:${align[j]}"` : ''}>${inline(c, base)}</td>`).join('') + '</tr>';
        i++;
      }
      html.push(t + '</tbody></table>');
      continue;
    }
    if (/^\s*>/.test(line)) {
      flush();
      const body = [];
      while (i < lines.length && /^\s*>/.test(lines[i])) body.push(lines[i++].replace(/^\s*>\s?/, ''));
      html.push(`<blockquote>${renderMarkdown(body.join('\n'), base)}</blockquote>`);
      continue;
    }
    const item = line.match(/^(\s*)([-*+]|\d+[.)])\s+(.*)$/);
    if (item) {
      flush();
      // Collect the items first so that text wrapped onto following lines
      // belongs to its item (bold or code spans can cross the line break).
      const items = [];
      while (i < lines.length) {
        const m = lines[i].match(/^(\s*)([-*+]|\d+[.)])\s+(.*)$/);
        if (m) {
          items.push({ indent: m[1].length, ordered: /\d/.test(m[2]), text: m[3] });
          i++;
          continue;
        }
        if (lines[i].trim() === '') {
          const next = lines.slice(i + 1).find((l) => l.trim() !== '');
          if (next && /^(\s*)([-*+]|\d+[.)])\s+/.test(next)) { i++; continue; }
          break;
        }
        if (/^\s+\S/.test(lines[i]) || !/^(#|>|\||```|~~~)/.test(lines[i].trim())) {
          items[items.length - 1].text += ' ' + lines[i].trim();
          i++;
          continue;
        }
        break;
      }
      const stack = [];
      for (const it of items) {
        const text = it.text.replace(/^\[( |x)\]\s+/i, (mm, c) => (c.trim() ? '☑ ' : '☐ '));
        if (!stack.length || it.indent > stack[stack.length - 1].indent) {
          stack.push(it);
          html.push(it.ordered ? '<ol>' : '<ul>');
        } else {
          while (stack.length > 1 && it.indent < stack[stack.length - 1].indent) {
            const top = stack.pop();
            html.push('</li>' + (top.ordered ? '</ol>' : '</ul>'));
          }
          html.push('</li>');
        }
        html.push('<li>' + inline(text, base));
      }
      while (stack.length) { const top = stack.pop(); html.push('</li>' + (top.ordered ? '</ol>' : '</ul>')); }
      continue;
    }
    if (line.trim() === '') { flush(); i++; continue; }
    para.push(line.trim());
    i++;
  }
  flush();
  return html.join('\n');
}
