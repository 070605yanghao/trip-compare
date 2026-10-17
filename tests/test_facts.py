# -*- coding: utf-8 -*-
"""信息状态测试：明确包含 / 明确不包含 / 未提及 / 模糊表述 / 重复关键词。

用法：python tests/test_facts.py  或  pytest tests/
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from trip_compare.extract import Doc
from trip_compare.parser import parse
from trip_compare.schema import (
    STATUS_AMBIGUOUS,
    STATUS_EXCLUDED,
    STATUS_INCLUDED,
    STATUS_UNKNOWN,
)


def _parse(text: str, name: str = "T") -> "object":
    return parse(Doc(path=name + ".txt", pages=[text]))


# ---------- 1. 明确包含 ----------

def test_included_skiing():
    p = _parse("产品亮点\n含 4 小时滑雪体验，赠送雪具。\n第一天：成都-西岭雪山")
    assert p.fact("滑雪").status == STATUS_INCLUDED, p.fact("滑雪")
    assert "滑雪" in p.fact("滑雪").value


def test_included_photography():
    p = _parse("赠送九寨沟旅拍 9 张精修 + 底片全送。")
    assert p.fact("旅拍").status == STATUS_INCLUDED
    assert "旅拍" in p.fact("旅拍").value


# ---------- 2. 明确不包含（不能被当成「未提取到」，也不能被误写成「自理」） ----------

def test_excluded_skiing_not_mislabeled():
    """「滑雪：不含」必须判为明确不包含，且不能沿用旧逻辑写成「雪票自理」。"""
    p = _parse("费用说明\n滑雪：不含。")
    f = p.fact("滑雪")
    assert f.status == STATUS_EXCLUDED, f
    assert "不含" in f.value
    assert "自理" not in f.value, f"不应臆造「自理」字样：{f.value}"


def test_excluded_photography():
    p = _parse("本产品不含旅拍，如需请自费。")
    assert p.fact("旅拍").status == STATUS_EXCLUDED


# ---------- 3. 未提及（不等于不包含） ----------

def test_unknown_skiing():
    p = _parse("第一天：成都-康定 住：康定【五钻】\n第二天：康定-成都散团")
    f = p.fact("滑雪")
    assert f.status == STATUS_UNKNOWN, f
    assert f.value == "", "未提及时结论应为空"
    assert p.skiing == "", "字符串字段也应为空"


def test_unknown_is_not_treated_as_absent():
    """未提及在报告里必须显示成「未提及」，而不是「—」或「不含」。"""
    from trip_compare.compare import matrix

    a = _parse("含 4 小时滑雪体验。", "A")
    b = _parse("第一天：成都-康定", "B")
    rows = dict(matrix([a, b]))
    assert rows["滑雪"][0] != "未提及"
    assert rows["滑雪"][1] == "未提及"


# ---------- 4. 模糊表述 ----------

def test_ambiguous_when_positive_and_negative_coexist():
    """「含滑雪体验，雪票自理」既含又不含 —— 应判模糊，而不是二选一。"""
    p = _parse("含 4 小时滑雪体验，雪票自理。")
    f = p.fact("滑雪")
    assert f.status == STATUS_AMBIGUOUS, f
    assert len(f.evidence) >= 1


def test_ambiguous_when_only_keyword_mentioned():
    """只出现地名「滑雪场」而无肯定/否定表述 —— 不能断定包含。"""
    p = _parse("途经西岭滑雪场，可自由活动。")
    f = p.fact("滑雪")
    assert f.status == STATUS_AMBIGUOUS, f
    assert f.status != STATUS_INCLUDED


# ---------- 5. 重复关键词 / 分类错误 ----------

def test_gifts_dedupe_and_no_duplicate():
    """同一句出现两次「赠送」应按子句拆开，且不能产生包含关系的重复条目。"""
    p = _parse("赠送无人机航拍一段，赠送藏装旅拍 6 张，赠送旅拍。")
    assert len(p.gifts) >= 2, p.gifts
    for a in p.gifts:
        for b in p.gifts:
            if a != b:
                assert a not in b, f"存在包含式重复：{a!r} ⊂ {b!r}"


def test_self_pay_not_misclassified_as_gift():
    """「雪票自理」属于需自理，绝不能进赠送项。"""
    p = _parse("赠送藏装旅拍 6 张，雪票自理。")
    assert any("自理" in s for s in p.self_pay), p.self_pay
    assert not any("自理" in g for g in p.gifts), f"自理项混进了赠送：{p.gifts}"


def test_gift_not_misclassified_as_self_pay():
    p = _parse("赠送无人机航拍一段。\n正餐自理。")
    assert any("航拍" in g for g in p.gifts), p.gifts
    assert not any("航拍" in s for s in p.self_pay), p.self_pay


def test_evidence_preserved():
    """重要字段必须保留原文依据，便于人工核实。"""
    p = _parse("费用说明\n滑雪：不含。")
    assert p.fact("滑雪").evidence, "缺少原文依据"
    assert any("滑雪" in e for e in p.fact("滑雪").evidence)


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    failed = 0
    for fn in fns:
        try:
            fn()
            print(f"  PASS  {fn.__name__}")
        except AssertionError as e:
            failed += 1
            print(f"  FAIL  {fn.__name__}: {e}")
    print(f"\n{len(fns) - failed}/{len(fns)} passed")
    sys.exit(1 if failed else 0)
