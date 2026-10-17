# -*- coding: utf-8 -*-
"""把多个产品拼成对比矩阵，并找出「独家项」。"""
from __future__ import annotations

from collections import Counter

from .schema import TripProduct


def matrix(products: list[TripProduct]) -> list[tuple[str, list[str]]]:
    """返回 [(维度名, [每个产品的值]), ...]"""
    def dur(p: TripProduct) -> str:
        return p.duration()

    def route(p: TripProduct) -> str:
        return " → ".join(p.route[:10]) if p.route else "—"

    def gifts(p: TripProduct) -> str:
        if not p.gifts:
            return "—"
        shown = p.gifts[:4]
        tail = f"（共 {len(p.gifts)} 项）" if len(p.gifts) > 4 else ""
        return "；".join(shown) + tail

    rows = [
        ("行程天数", [dur(p) for p in products]),
        ("团型", [p.group_size or "—" for p in products]),
        ("用车", [p.vehicle or "—" for p in products]),
        ("住宿配置", [p.stay_summary() for p in products]),
        ("行程覆盖", [route(p) for p in products]),
        ("滑雪", [p.skiing or "—" for p in products]),
        ("旅拍", [p.photography or "—" for p in products]),
        ("赠送项目", [gifts(p) for p in products]),
        ("需自理", ["；".join(p.self_pay[:3]) if p.self_pay else "—" for p in products]),
        ("定位人群", [p.audience or "—" for p in products]),
    ]
    return rows


_COMPARABLE = {"行程天数", "用车", "滑雪", "旅拍", "住宿配置", "定位人群"}


def unique_cells(rows: list[tuple[str, list[str]]]) -> set[tuple[int, int]]:
    """在可比较的维度上找出「只有一家」的值，返回 (row_idx, col_idx) 集合，用于高亮。"""
    marks: set[tuple[int, int]] = set()
    for ri, (name, values) in enumerate(rows):
        if name not in _COMPARABLE:
            continue
        valid = [v for v in values if v != "—"]
        if len(valid) < 2:
            continue
        cnt = Counter(valid)
        for ci, v in enumerate(values):
            if v != "—" and cnt.get(v) == 1:
                marks.add((ri, ci))
    return marks
