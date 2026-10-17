# -*- coding: utf-8 -*-
"""把多个产品拼成对比矩阵，并找出「独家项」。"""
from __future__ import annotations

from collections import Counter

from .schema import STATUS_INCLUDED, STATUS_UNKNOWN, Fact, TripProduct

# 展示时的占位符：区分「原文没写」和「写了没有」
NA = "—"
UNKNOWN_TEXT = "未提及"


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

    def gifts(p: TripProduct) -> str:
        f = p.fact("赠送项目")
        if f.status == STATUS_UNKNOWN:
            return UNKNOWN_TEXT
        if not p.gifts:
            return f"{f.mark} {f.label}"
        shown = p.gifts[:4]
        tail = f"（共 {len(p.gifts)} 项）" if len(p.gifts) > 4 else ""
        return "；".join(shown) + tail

    def self_pay(p: TripProduct) -> str:
        if p.self_pay:
            return "；".join(p.self_pay[:3])
        f = p.fact("需自理")
        return UNKNOWN_TEXT if f.status == STATUS_UNKNOWN else f"{f.mark} {f.label}"

    def by_fact(dim: str, fallback: str = "") -> "callable":
        def _f(p: TripProduct) -> str:
            f = p.fact(dim)
            if f.status == STATUS_UNKNOWN:
                return UNKNOWN_TEXT
            return _fact_text(f) or fallback or NA
        return _f

    rows = [
        ("行程天数", [dur(p) for p in products]),
        ("团型", [by_fact("团型", p.group_size)(p) for p in products]),
        ("用车", [by_fact("用车", p.vehicle)(p) for p in products]),
        ("住宿配置", [p.stay_summary() for p in products]),
        ("行程覆盖", [route(p) for p in products]),
        ("滑雪", [by_fact("滑雪", p.skiing)(p) for p in products]),
        ("旅拍", [by_fact("旅拍", p.photography)(p) for p in products]),
        ("赠送项目", [gifts(p) for p in products]),
        ("需自理", [self_pay(p) for p in products]),
        ("定位人群", [by_fact("定位人群", p.audience)(p) for p in products]),
    ]
    return rows


def facts_by_dim(products: list[TripProduct]) -> dict[str, list[Fact]]:
    """{(行号, 维度名): [每个产品的 Fact]} —— report 用它渲染状态与原文依据。"""
    dims = [name for name, _ in matrix(products)]
    return {name: [p.fact(name) for p in products] for name in dims}


_COMPARABLE = {"行程天数", "用车", "滑雪", "旅拍", "住宿配置", "定位人群"}


def unique_cells(rows: list[tuple[str, list[str]]]) -> set[tuple[int, int]]:
    """在可比较的维度上找出「只有一家」的值，返回 (row_idx, col_idx) 集合，用于高亮。

    只有「明确包含」的单元格才参与独家项比较；未提及/无法确认不参与，
    否则会把「原文没写」误判成「这家没有」。
    """
    marks: set[tuple[int, int]] = set()
    for ri, (name, values) in enumerate(rows):
        if name not in _COMPARABLE:
            continue
        valid = [v for v in values if v not in (NA, UNKNOWN_TEXT)]
        if len(valid) < 2:
            continue
        cnt = Counter(valid)
        for ci, v in enumerate(values):
            if v not in (NA, UNKNOWN_TEXT) and cnt.get(v) == 1:
                marks.add((ri, ci))
    return marks
