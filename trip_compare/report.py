# -*- coding: utf-8 -*-
"""HTML 对比报告渲染（零依赖，内嵌样式）。"""
from __future__ import annotations

import html
from datetime import datetime

from .compare import matrix, unique_cells
from .schema import TripProduct

_CSS = """
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:-apple-system,"Segoe UI","PingFang SC","Microsoft YaHei",sans-serif;
     background:#f4f7fd;color:#111a2e;line-height:1.65}
header{background:linear-gradient(135deg,#0b2a6b,#1557e8 55%,#3d7dff);color:#fff;padding:44px 0 38px}
.hwrap{max-width:1240px;margin:0 auto;padding:0 24px}
h1{font-size:30px;font-weight:800}
h1 span{color:#ffd08a}
.sub{margin-top:10px;font-size:14px;color:rgba(255,255,255,.8)}
.meta{margin-top:14px;font-size:12px;color:rgba(255,255,255,.6)}
.wrap{max-width:1240px;margin:0 auto;padding:0 24px 64px}
section{margin-top:40px}
.stitle{display:flex;align-items:center;gap:10px;margin-bottom:16px}
.stitle .bar{width:4px;height:20px;border-radius:3px;background:#1557e8}
.stitle h2{font-size:19px;font-weight:800}
.stitle small{font-size:12px;color:#77809a}
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(230px,1fr));gap:14px}
.card{background:#fff;border:1px solid #e3e8f2;border-radius:14px;padding:16px;position:relative;overflow:hidden}
.card .cbar{position:absolute;inset:0 0 auto 0;height:4px;background:linear-gradient(90deg,#1557e8,#5b93ff)}
.card .code{font-size:11px;font-weight:700;letter-spacing:1px;color:#77809a}
.card h3{font-size:15px;font-weight:800;margin:4px 0 8px;line-height:1.4}
.card .days{display:inline-block;font-size:11px;font-weight:700;padding:2px 9px;border-radius:6px;
            background:#eaf0ff;color:#1557e8}
.card p{font-size:12px;color:#3c4761;margin-top:8px}
.tblbox{background:#fff;border:1px solid #e3e8f2;border-radius:14px;overflow-x:auto}
table{width:100%;border-collapse:collapse;font-size:13px;min-width:720px}
thead th{background:linear-gradient(180deg,#0f3fa8,#1557e8);color:#fff;padding:12px;text-align:left;
         font-size:12.5px;vertical-align:top;border-right:1px solid rgba(255,255,255,.14)}
thead th:first-child{width:110px}
thead .code{display:block;font-size:10px;opacity:.7}
tbody th{text-align:left;background:#f5f8ff;padding:11px 12px;border-bottom:1px solid #e3e8f2;
         border-right:1px solid #e3e8f2;font-size:12px;font-weight:700;vertical-align:top;white-space:nowrap}
tbody td{padding:11px 12px;border-bottom:1px solid #e3e8f2;border-right:1px solid #eef2f9;
         color:#3c4761;vertical-align:top;line-height:1.6;font-size:12.5px}
tbody tr:hover td{background:#fafcff}
td.best{background:#eef4ff;color:#0e3fae;font-weight:600}
.na{color:#b6bfd4}
footer{margin-top:36px;padding-top:16px;border-top:1px solid #e3e8f2;font-size:11.5px;color:#77809a}
.badge{display:inline-block;font-size:10px;font-weight:700;padding:1px 7px;border-radius:5px;
       background:#fff1e6;color:#d95f04;margin-left:4px}
"""

_CARD_COLORS = ["#1557e8", "#6b4de6", "#f9741a", "#0ea5a5", "#c0392b", "#5b7f2a"]


def _esc(s: str) -> str:
    return html.escape(s or "")


def render(products: list[TripProduct], title: str = "行程对比报告") -> str:
    rows = matrix(products)
    marks = unique_cells(rows)
    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    cards = []
    for i, p in enumerate(products):
        color = _CARD_COLORS[i % len(_CARD_COLORS)]
        badge = '<span class="badge">LLM</span>' if p.extractor == "llm" else ""
        cards.append(
            f'<div class="card"><div class="cbar" style="background:{color}"></div>'
            f'<div class="code">{_esc(p.code) or _esc(p.source_file)}</div>'
            f"<h3>{_esc(p.title)}{badge}</h3>"
            f'<div class="days">{_esc(p.duration())}</div>'
            f"<p>{_esc(p.stay_summary())}</p></div>"
        )

    head_cells = "".join(
        f'<th><span class="code">{_esc(p.code) or _esc(p.source_file)}</span>{_esc(p.title)}</th>'
        for p in products
    )
    body_rows = []
    for ri, (dim, values) in enumerate(rows):
        cells = []
        for ci, v in enumerate(values):
            cls = "best" if (ri, ci) in marks else ("na" if v == "—" else "")
            cells.append(f'<td class="{cls}">{_esc(v)}</td>')
        body_rows.append(f"<tr><th>{_esc(dim)}</th>{''.join(cells)}</tr>")

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{_esc(title)}</title>
<style>{_CSS}</style>
</head>
<body>
<header><div class="hwrap">
  <h1>{_esc(title)} · <span>共同点 &amp; 差异点</span></h1>
  <p class="sub">自动从 {len(products)} 份产品说明书中提取结构化字段，生成对比矩阵。高亮单元格 = 该维度上的独家项。</p>
  <p class="meta">生成时间：{now} ｜ trip-compare</p>
</div></header>
<div class="wrap">
  <section>
    <div class="stitle"><div class="bar"></div><h2>产品速览</h2><small>{len(products)} 款</small></div>
    <div class="cards">{''.join(cards)}</div>
  </section>
  <section>
    <div class="stitle"><div class="bar"></div><h2>对比矩阵</h2><small>★ 蓝底 = 独家项</small></div>
    <div class="tblbox"><table>
      <thead><tr><th>对比维度</th>{head_cells}</tr></thead>
      <tbody>{''.join(body_rows)}</tbody>
    </table></div>
  </section>
  <footer>
    由 trip-compare 自动生成 ｜ 提取方式：{', '.join(sorted({p.extractor for p in products}))}
    ｜ 数据以原始说明书为准
  </footer>
</div>
</body>
</html>"""
