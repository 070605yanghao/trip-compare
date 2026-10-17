# -*- coding: utf-8 -*-
"""HTML 对比报告渲染（零依赖，内嵌样式）。"""
from __future__ import annotations

import html
from datetime import datetime

from .compare import (
    EXCLUDED_LABEL,
    INCLUDED_LABEL,
    NA,
    UNKNOWN_TEXT,
    cell_marks,
    facts_by_dim,
    matrix,
    status_label,
    summary_lines,
)
from .schema import STATUS_EXCLUDED, STATUS_INCLUDED, STATUS_UNKNOWN, Fact, TripProduct

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
/* 信息状态标记：✓含 / ✗不含 / ?未提及 / ~待确认 */
.st{display:inline-block;font-size:10px;font-weight:700;padding:1px 6px;border-radius:5px;
    margin-right:5px;vertical-align:1px}
.st-included{background:#e6f6ec;color:#18794e}
.st-excluded{background:#fdeaea;color:#b4232a}
.st-unknown{background:#eef0f5;color:#8089a3}
.st-ambiguous{background:#fff4e0;color:#b06a00}
.ev{display:block;margin-top:5px;padding-left:8px;border-left:2px solid #dde4f2;
    font-size:11px;color:#8a93ab;line-height:1.5}
.legend{margin-top:10px;font-size:11.5px;color:#77809a}
.legend b{font-weight:700}
td.diff{background:#f6f8fc;color:#3c4761;font-weight:600}
td.unique{background:#eef4ff;color:#0e3fae;font-weight:600}
.tag{display:inline-block;font-size:9.5px;font-weight:700;padding:0 5px;border-radius:4px;
     margin-left:5px;vertical-align:1px}
.tag-unique{background:#dbe7ff;color:#1557e8}
.tag-diff{background:#eceff5;color:#7b8499}
.sumbox{background:#fff;border:1px solid #e3e8f2;border-radius:14px;padding:16px 18px}
.sumbox ul{list-style:none;margin:0;padding:0}
.sumbox li{font-size:12.5px;color:#3c4761;padding:6px 0;border-bottom:1px dashed #eef2f9;line-height:1.6}
.sumbox li:last-child{border-bottom:0}
.sumbox li.warn{color:#b06a00}
"""

_CARD_COLORS = ["#1557e8", "#6b4de6", "#f9741a", "#0ea5a5", "#c0392b", "#5b7f2a"]


_LIST_DIMS = {"赠送项目", "需自理", "包含服务"}


def _esc(s: str) -> str:
    return html.escape(s or "")


def _status_chip(f: Fact, dim: str = "", label: str = "") -> str:
    """状态标记；文案按字段调整（赠送/自费不用「明确包含」这种笼统说法）。"""
    if f.status == STATUS_UNKNOWN and not f.value:
        return '<span class="st st-unknown">? 未提及</span>'
    return f'<span class="st st-{f.status}">{f.mark} {label or f.label}</span>'


def _evidence_html(f: Fact, limit: int = 3) -> str:
    """原文依据。超出 limit 时明确写出总数，避免「显示了 4 项、只给 3 条依据」的错觉。"""
    if not f.evidence:
        return ""
    items = "".join(f"<div>“{_esc(_clip_ev(e))}”</div>" for e in f.evidence[:limit])
    more = ""
    if len(f.evidence) > limit:
        more = f'<div>… 共 {len(f.evidence)} 条原文依据</div>'
    return f'<span class="ev">{items}{more}</span>'


_BRACKET_PAIR = {"（": "）", "(": ")", "【": "】", "[": "]", "《": "》", "<": ">"}


def _clip_ev(s: str, n: int = 46) -> str:
    """原文依据的展示截断：补「…」，并回退掉尾部未闭合的括号。

    避免出现「川西环线 8 天 7 晚私家团（样品数据」这种残缺标题；
    原始证据内容本身不修改，这里只是展示层的裁剪。
    """
    s = (s or "").strip()
    if len(s) <= n:
        return s
    head = s[: n - 1]
    # 用栈找出「最外层第一个没有闭合的开启括号」，从它之前裁断，
    # 保证裁剪结果里所有括号都是配对的（只回退最后一段是不够的）
    stack: list[int] = []
    for i, ch in enumerate(head):
        if ch in _BRACKET_PAIR:
            stack.append(i)
        elif ch in _BRACKET_PAIR.values() and stack:
            stack.pop()
    if stack:
        head = head[: stack[0]]
    return head.rstrip() + "…"


def render(products: list[TripProduct], title: str = "行程对比报告") -> str:
    rows = matrix(products)
    marks = cell_marks(products, rows)
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
    fmap = facts_by_dim(products)
    for ri, (dim, values) in enumerate(rows):
        cells = []
        for ci, v in enumerate(values):
            kind = marks.get((ri, ci))
            cls = kind if kind else ("na" if v in (NA, UNKNOWN_TEXT) else "")
            chip = ""
            ev = ""
            fl = fmap.get(dim) or []
            if ci < len(fl):
                f = fl[ci]
                if f is not None:
                    # 列表型字段（赠送/自理/包含服务）只在「未提及」时打状态标记，
                    # 否则「✓ 明确包含：晚餐自理」读起来是错的
                    lab = status_label(products[ci], dim)
                    if dim in _LIST_DIMS:
                        if f.status == STATUS_UNKNOWN:
                            chip = _status_chip(f, dim, lab)
                    elif f.status != STATUS_UNKNOWN or f.value:
                        chip = _status_chip(f, dim, lab)
                    ev = _evidence_html(f)
            tag = ""
            if kind == "unique":
                tag = '<span class="tag tag-unique">独家</span>'
            elif kind == "diff":
                tag = '<span class="tag tag-diff">差异</span>'
            cells.append(f'<td class="{cls}">{chip}{_esc(v)}{tag}{ev}</td>')
        body_rows.append(f"<tr><th>{_esc(dim)}</th>{''.join(cells)}</tr>")

    summary = "".join(
        f'<li class="{"warn" if line.startswith("提示") else ""}">{_esc(line)}</li>'
        for line in summary_lines(products)
    )

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
  <p class="sub">自动从 {len(products)} 份产品说明书中提取结构化字段，生成对比矩阵；
    并区分「独家服务」与「属性差异」，每条结论附原文依据。</p>
  <p class="meta">生成时间：{now} ｜ trip-compare</p>
</div></header>
<div class="wrap">
  <section>
    <div class="stitle"><div class="bar"></div><h2>产品速览</h2><small>{len(products)} 款</small></div>
    <div class="cards">{''.join(cards)}</div>
  </section>
  <section>
    <div class="stitle"><div class="bar"></div><h2>核心差异摘要</h2><small>仅陈述提取到的事实</small></div>
    <div class="sumbox"><ul>{summary}</ul></div>
  </section>
  <section>
    <div class="stitle"><div class="bar"></div><h2>对比矩阵</h2><small>独家 = 有双向证据 ｜ 差异 = 属性不同</small></div>
    <div class="tblbox"><table>
      <thead><tr><th>对比维度</th>{head_cells}</tr></thead>
      <tbody>{''.join(body_rows)}</tbody>
    </table></div>
    <p class="legend">
      <b>状态说明：</b>✓ 明确包含/赠送/提供 ｜ ✗ 明确不包含、需自理或需自费 ｜ ? 原文未提及（不等于不包含）｜ ~ 表述模糊或自相矛盾，需人工确认。
      <b>标记说明：</b><span class="tag tag-unique">独家</span> 仅在该产品明确包含、且其他产品明确不包含时给出；
      <span class="tag tag-diff">差异</span> 只表示客观属性取值不同，不代表某产品独有或更优。
      灰色小字为对应原文依据；未提及项不参与独家判定。
    </p>
  </section>
  <footer>
    由 trip-compare 自动生成 ｜ 提取方式：{', '.join(sorted({p.extractor for p in products}))}
    ｜ 数据以原始说明书为准
  </footer>
</div>
</body>
</html>"""
