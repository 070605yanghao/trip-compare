# -*- coding: utf-8 -*-
"""把多个产品拼成对比矩阵，并判断「独家服务」与「属性差异」。

两条独立的概念，不能混为一谈：
- 独家服务：某产品「明确包含」且其他产品「明确不包含/需自费」——需要双向证据；
- 属性差异：行程天数、团型、用车这类客观属性不同——只说明不同，不代表谁更好、谁独有。
"""
from __future__ import annotations

import re
from collections import Counter

from .schema import (
    CAT_EXCLUDED,
    CAT_GIFT,
    CAT_INCLUDED,
    CAT_PHOTO,
    CAT_SELF_PAY,
    CAT_SKIING,
    STATUS_EXCLUDED,
    STATUS_INCLUDED,
    STATUS_UNKNOWN,
    Fact,
    TripProduct,
)

# 展示时的占位符：区分「原文没写」和「写了没有」
NA = "—"
UNKNOWN_TEXT = "未提及"

# 一个维度最多展示/取证几条：展示条数 == 依据条数，避免「显示了 4 项、只给 3 条依据」
MAX_SHOW = 4

DIM_VEHICLE = "用车"
DIM_GROUP = "团型"
DIM_SKIING = "滑雪"
DIM_PHOTO = "旅拍"
DIM_AUDIENCE = "定位人群"
DIM_GIFTS = "赠送项目"
DIM_SELF_PAY = "需自理"
DIM_INCLUDED = "包含服务"
DIM_DURATION = "行程天数"
DIM_STAYS = "住宿配置"
DIM_ROUTE = "行程覆盖"

# 类别 -> 展示维度（一条事实只落一个维度，避免重复展示）
DIM_OF_CAT = {
    CAT_SKIING: DIM_SKIING,
    CAT_PHOTO: DIM_PHOTO,
    CAT_GIFT: DIM_GIFTS,
    CAT_SELF_PAY: DIM_SELF_PAY,
    CAT_EXCLUDED: DIM_SELF_PAY,
    CAT_INCLUDED: DIM_INCLUDED,
}

# 服务类维度：只有这些维度才可能判定「独家服务」
SERVICE_DIMS = {DIM_SKIING, DIM_PHOTO, DIM_GIFTS, DIM_INCLUDED, DIM_SELF_PAY}
# 客观属性维度：只做差异提示，不称为独家
PROPERTY_DIMS = {"行程天数", DIM_GROUP, DIM_VEHICLE, "住宿配置", "行程覆盖", DIM_AUDIENCE}

# 各维度「明确包含」时的文案（不同字段用更准确的说法）
INCLUDED_LABEL = {
    DIM_GIFTS: "明确赠送",
    DIM_INCLUDED: "明确包含",
    DIM_SKIING: "明确包含",
    DIM_PHOTO: "明确包含",
    DIM_VEHICLE: "明确提供",
    DIM_GROUP: "明确说明",
    DIM_AUDIENCE: "明确说明",
    DIM_DURATION: "明确说明",
    DIM_STAYS: "明确提供",
    DIM_ROUTE: "明确说明",
}
EXCLUDED_LABEL = {
    DIM_SELF_PAY: "明确需自理/自费/不含",
    DIM_GIFTS: "明确不赠送",
}

# 「自理」= 不含、需自行安排；「自费」= 明确要另外掏钱。两者口径不同，不能一律写成「需自费」。
_PAY_KW = re.compile(r"自费|需另付|另行付费|自行购买|另付费")
_OWN_KW = re.compile(r"自理|需自理|费用自理|自行安排")


def clip_text(s: str, n: int) -> str:
    """展示用截断：仅在真的截断时补「…」，不改动底层数据（结构化数据仍是完整值）。"""
    s = (s or "").strip()
    return s if len(s) <= n else s[: n - 1].rstrip() + "…"


def status_label(p: TripProduct, dim: str) -> str:
    """按字段给出更准确的文案：赠送的就说「明确赠送」，自费的说「明确需自费」。"""
    f = p.fact(dim)
    if f.status == STATUS_INCLUDED:
        its = [i for i in p.items_of(dim)]
        if its and all(i.has(CAT_GIFT) for i in its):
            return "明确赠送"
        return INCLUDED_LABEL.get(dim, f.label)
    if f.status == STATUS_EXCLUDED:
        its = [i for i in p.items_of(dim)]
        if dim == DIM_SELF_PAY and its:
            if all(_PAY_KW.search(i.text) for i in its):
                return "明确需自费"
            if all(_OWN_KW.search(i.text) for i in its):
                return "明确需自理"
            return "明确需自理/自费"
        return EXCLUDED_LABEL.get(dim, f.label)
    return f.label


def _fact_text(f: Fact) -> str:
    """把 Fact 变成表格里显示的文本（状态标记由 report 的 chip 负责，此处不重复）。"""
    if f.status == STATUS_UNKNOWN:
        return UNKNOWN_TEXT
    return f.value or NA


def matrix(products: list[TripProduct]) -> list[tuple[str, list[str]]]:
    """返回 [(维度名, [每个产品的值]), ...]"""
    def dur(p: TripProduct) -> str:
        return p.duration()

    def route(p: TripProduct) -> str:
        return " → ".join(p.route[:10]) if p.route else NA

    def list_dim(dim: str) -> "callable":
        def _f(p: TripProduct) -> str:
            texts = [it.text for it in p.items_of(dim)]
            if texts:
                shown = texts[:MAX_SHOW]
                tail = f"（共 {len(texts)} 项）" if len(texts) > MAX_SHOW else ""
                return "；".join(shown) + tail
            f = p.fact(dim)
            if f.status == STATUS_UNKNOWN:
                return UNKNOWN_TEXT
            return f.value or NA
        return _f

    def fact_dim(dim: str, fallback: str = "") -> "callable":
        def _f(p: TripProduct) -> str:
            f = p.fact(dim)
            if f.status == STATUS_UNKNOWN:
                return UNKNOWN_TEXT
            return f.value or fallback or NA
        return _f

    rows = [
        ("行程天数", [dur(p) for p in products]),
        ("团型", [fact_dim("团型", p.group_size)(p) for p in products]),
        ("用车", [fact_dim("用车", p.vehicle)(p) for p in products]),
        ("住宿配置", [p.stay_summary() for p in products]),
        ("行程覆盖", [route(p) for p in products]),
        ("滑雪", [fact_dim("滑雪", p.skiing)(p) for p in products]),
        ("旅拍", [fact_dim("旅拍", p.photography)(p) for p in products]),
        ("赠送项目", [list_dim("赠送项目")(p) for p in products]),
        ("包含服务", [list_dim("包含服务")(p) for p in products]),
        ("需自理", [list_dim("需自理")(p) for p in products]),
        ("定位人群", [fact_dim("定位人群", p.audience)(p) for p in products]),
    ]
    return rows


def facts_by_dim(products: list[TripProduct]) -> dict[str, list[Fact]]:
    """{维度名: [每个产品的 Fact]} —— report 用它渲染状态与原文依据。"""
    dims = [name for name, _ in matrix(products)]
    return {name: [p.fact(name) for p in products] for name in dims}


def cell_marks(products: list[TripProduct], rows: list[tuple[str, list[str]]]) -> dict[tuple[int, int], str]:
    """返回 {(row_idx, col_idx): 'unique' | 'diff'}。

    unique = 独家服务：本品明确包含，且其他所有产品都明确不包含/需自费。
    diff   = 属性差异：客观属性取值不同，仅提示，不称为独家。
    未提及 / 模糊 的单元格一律不参与判定——证据不足时不标独家。
    """
    marks: dict[tuple[int, int], str] = {}
    n = len(products)
    if n < 2:
        return marks

    for ri, (name, _) in enumerate(rows):
        facts = [p.fact(name) for p in products]
        if name in SERVICE_DIMS:
            for ci, f in enumerate(facts):
                if f.status != STATUS_INCLUDED:
                    continue
                others = [facts[j] for j in range(n) if j != ci]
                # 只有其他产品都「明确不包含」时才算独家；未提及/模糊 => 证据不足
                if others and all(o.status == STATUS_EXCLUDED for o in others):
                    marks[(ri, ci)] = "unique"
        elif name in PROPERTY_DIMS:
            values = rows[ri][1]
            valid = [v for v in values if v not in (NA, UNKNOWN_TEXT)]
            if len(valid) < 2:
                continue
            cnt = Counter(valid)
            for ci, v in enumerate(values):
                if v not in (NA, UNKNOWN_TEXT) and cnt.get(v) == 1:
                    marks[(ri, ci)] = "diff"
    return marks


def unique_cells(rows: list[tuple[str, list[str]]]) -> set[tuple[int, int]]:
    """兼容旧接口：只返回「属性差异」单元格，独家判定请用 cell_marks。"""
    marks: set[tuple[int, int]] = set()
    for ri, (name, values) in enumerate(rows):
        if name not in PROPERTY_DIMS:
            continue
        valid = [v for v in values if v not in (NA, UNKNOWN_TEXT)]
        if len(valid) < 2:
            continue
        cnt = Counter(valid)
        for ci, v in enumerate(values):
            if v not in (NA, UNKNOWN_TEXT) and cnt.get(v) == 1:
                marks.add((ri, ci))
    return marks


def summary_lines(products: list[TripProduct]) -> list[str]:
    """核心差异摘要：只陈述提取到的事实，不做推荐、不编造。"""
    lines: list[str] = []

    def name(p: TripProduct) -> str:
        return p.code or p.source_file

    def join_vals(fn) -> str:
        return " ｜ ".join(f"{name(p)}：{fn(p)}" for p in products)

    # 行程时长
    durs = [p.duration() for p in products]
    if len(set(durs)) > 1:
        lines.append("行程时长不同：" + join_vals(lambda p: p.duration()))
    else:
        lines.append("行程时长相同：" + durs[0])

    # 团型 / 用车
    for dim in ("团型", "用车"):
        vals = [p.fact(dim).value or UNKNOWN_TEXT for p in products]
        st = [p.fact(dim).status for p in products]
        if any(s == STATUS_UNKNOWN for s in st):
            lines.append(f"{dim}：部分产品原文未提及，无法完整比较（" + join_vals(
                lambda p, d=dim: (p.fact(d).value or UNKNOWN_TEXT)) + "）")
        elif len(set(vals)) > 1:
            lines.append(f"{dim}不同：" + join_vals(lambda p, d=dim: p.fact(d).value))
        else:
            lines.append(f"{dim}一致：{vals[0]}")

    # 住宿（stays 是去重后的住宿地点，不等于晚数，措辞要准确）
    lines.append("住宿：" + join_vals(lambda p: (
        f"提取到 {len(p.stays)} 处（{clip_text(p.stay_summary(), 30)}）" if p.stays else UNKNOWN_TEXT)))

    # 特色体验（滑雪 / 旅拍）：按状态陈述，不下结论
    for dim in (DIM_SKIING, DIM_PHOTO):
        parts = []
        for p in products:
            f = p.fact(dim)
            if f.status == STATUS_UNKNOWN:
                parts.append(f"{name(p)}：{UNKNOWN_TEXT}")
            else:
                parts.append(f"{name(p)}：{status_label(p, dim)}（{clip_text(f.value, 24)}）")
        lines.append(f"{dim}：" + " ｜ ".join(parts))

    # 费用相关：赠送按全部 gift 事实计数（它们可能展示在旅拍/滑雪维度里）
    fee = []
    for p in products:
        g = len([i for i in p.items if i.has(CAT_GIFT)])
        s = len([i for i in p.items_of(DIM_SELF_PAY)])
        inc = len([i for i in p.items_of(DIM_INCLUDED)])
        fee.append(f"{name(p)}：赠送 {g} 项 / 包含 {inc} 项 / 需自理或不包含 {s} 项")
    lines.append("费用相关：" + " ｜ ".join(fee))

    # 证据不足提示
    unknown_dims = []
    for dim in ("滑雪", "旅拍", "赠送项目", "包含服务", "需自理"):
        if any(p.fact(dim).status == STATUS_UNKNOWN for p in products):
            unknown_dims.append(dim)
    if unknown_dims:
        lines.append("提示：" + "、".join(sorted(set(unknown_dims)))
                     + " 在部分产品中原文未提及，不能据此认定其不提供该服务。")
    return lines
