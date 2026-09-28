"""Self-contained interactive HTML report."""

from __future__ import annotations

import html
import json

from datasift_diff.models import DiffResult


def render_html(result: DiffResult) -> str:
    data = json.dumps(result.to_dict(), ensure_ascii=False, default=str)
    s = result.summary

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>datasift-diff report</title>
<style>
:root {{
  --bg: #0d1117; --fg: #c9d1d9; --muted: #8b949e;
  --border: #30363d; --card: #161b22; --accent: #58a6ff;
  --added: #3fb950; --removed: #f85149; --changed: #d29922;
}}
* {{ box-sizing: border-box; }}
body {{
  margin: 0; padding: 0; background: var(--bg); color: var(--fg);
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
  font-size: 14px; line-height: 1.5;
}}
header {{
  padding: 24px; border-bottom: 1px solid var(--border); background: var(--card);
}}
h1 {{ margin: 0; font-size: 22px; }}
.subtitle {{ color: var(--muted); font-size: 13px; margin-top: 4px; }}
main {{ max-width: 1100px; margin: 0 auto; padding: 32px 24px; }}
.stats {{ display: flex; gap: 16px; margin-bottom: 24px; flex-wrap: wrap; }}
.stat {{
  flex: 1; min-width: 140px; padding: 16px; border-radius: 8px;
  background: var(--card); border: 1px solid var(--border);
}}
.stat .num {{ font-size: 28px; font-weight: 700; }}
.stat.added .num {{ color: var(--added); }}
.stat.removed .num {{ color: var(--removed); }}
.stat.changed .num {{ color: var(--changed); }}
.stat .label {{ color: var(--muted); font-size: 12px; text-transform: uppercase; }}
.toolbar {{ margin-bottom: 16px; display: flex; gap: 8px; flex-wrap: wrap; }}
.toolbar input {{
  flex: 1; min-width: 200px; padding: 8px 12px; background: var(--bg);
  color: var(--fg); border: 1px solid var(--border); border-radius: 6px;
}}
.toolbar button {{
  padding: 8px 16px; background: var(--card); color: var(--fg);
  border: 1px solid var(--border); border-radius: 6px; cursor: pointer;
}}
.toolbar button.active {{ border-color: var(--accent); color: var(--accent); }}
table {{ width: 100%; border-collapse: collapse; margin-bottom: 32px; }}
th, td {{ text-align: left; padding: 8px 12px; border-bottom: 1px solid var(--border); }}
th {{ color: var(--muted); font-size: 12px; text-transform: uppercase; }}
tr.hidden {{ display: none; }}
.tag {{
  display: inline-block; padding: 2px 8px; border-radius: 4px;
  font-size: 11px; font-weight: 600; text-transform: uppercase;
}}
.tag.added {{ background: rgba(63,185,80,.15); color: var(--added); }}
.tag.removed {{ background: rgba(248,81,73,.15); color: var(--removed); }}
.tag.changed {{ background: rgba(210,153,34,.15); color: var(--changed); }}
.field {{ color: var(--muted); font-family: monospace; }}
.old {{ color: var(--removed); font-family: monospace; }}
.new {{ color: var(--added); font-family: monospace; }}
</style>
</head>
<body>
<header>
  <h1>datasift-diff report</h1>
  <div class="subtitle">Key(s): {html.escape(", ".join(result.key_fields))}</div>
</header>
<main>
  <div class="stats">
    <div class="stat added"><div class="num">{s.added}</div><div class="label">Added</div></div>
    <div class="stat removed"><div class="num">{s.removed}</div><div class="label">Removed</div></div>
    <div class="stat changed"><div class="num">{s.changed}</div><div class="label">Changed</div></div>
  </div>

  <div class="toolbar">
    <input type="text" id="search" placeholder="Search key or field...">
    <button data-filter="all" class="active">All</button>
    <button data-filter="added">Added</button>
    <button data-filter="removed">Removed</button>
    <button data-filter="changed">Changed</button>
  </div>

  <table>
    <thead>
      <tr><th>Type</th><th>Key</th><th>Field</th><th>Old</th><th>New</th></tr>
    </thead>
    <tbody id="rows"></tbody>
  </table>
</main>
<script>
const DATA = {data};
const tbody = document.getElementById('rows');
const searchInput = document.getElementById('search');
const filterButtons = document.querySelectorAll('.toolbar button[data-filter]');
let currentFilter = 'all';

function esc(s) {{
  return String(s == null ? '' : s)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}}

function keyStr(change) {{
  if (change.key_values && change.key_values.length) {{
    return change.key_values.map(kv => kv.field + '=' + kv.value).join('|');
  }}
  return JSON.stringify(change.key);
}}

function render() {{
  const q = searchInput.value.toLowerCase();
  tbody.innerHTML = '';

  function addRow(type, change, field, oldV, newV) {{
    const key = keyStr(change);
    const row = document.createElement('tr');
    row.dataset.type = type;
    const matchesFilter = currentFilter === 'all' || currentFilter === type;
    const matchesSearch = !q ||
      key.toLowerCase().includes(q) ||
      (field || '').toLowerCase().includes(q);
    if (!matchesFilter || !matchesSearch) row.classList.add('hidden');
    row.innerHTML =
      '<td><span class="tag ' + type + '">' + type + '</span></td>' +
      '<td>' + esc(key) + '</td>' +
      '<td class="field">' + esc(field || '') + '</td>' +
      '<td class="old">' + esc(oldV) + '</td>' +
      '<td class="new">' + esc(newV) + '</td>';
    tbody.appendChild(row);
  }}

  DATA.added.forEach(c => addRow('added', c, '', '', ''));
  DATA.removed.forEach(c => addRow('removed', c, '', '', ''));
  DATA.changed.forEach(c => {{
    c.field_changes.forEach(fc => {{
      addRow('changed', c, fc.field, fc.old_value, fc.new_value);
    }});
  }});
}}

searchInput.addEventListener('input', render);
filterButtons.forEach(btn => {{
  btn.addEventListener('click', () => {{
    filterButtons.forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    currentFilter = btn.dataset.filter;
    render();
  }});
}});

render();
</script>
</body>
</html>
"""
