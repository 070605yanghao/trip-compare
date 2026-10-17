# -*- coding: utf-8 -*-
"""字段提取与分类测试：重复展示 / 一句话多事实拆分 / 误判 / 状态 / 独家 / 依据一致性 / 回归。

用法：python tests/test_extraction.py  或  pytest tests/
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from trip_compare.compare import (
    DIM_GIFTS,
    DIM_INCLUDED,
    DIM_PHOTO,
    DIM_SELF_PAY,
    DIM_SKIING,
    cell_marks,
    matrix,
    status_label,
)
from trip_compare.extract import Doc
from trip_compare.parser import extract_items, parse
from trip_compare.schema import (
    STATUS_EXCLUDED,
    STATUS_INCLUDED,
    STATUS_UNKNOWN,
    TripProduct,
)


def _parse(text: str, name: str = "T") -> TripProduct:
    return parse(Doc(path=name + ".txt", pages=[text]))


# ---------- 1. 重复展示：同一条「赠送旅拍」只在一个维度出现 ----------

def test_gift_photo_not_shown_twice():
    """「赠送无人机航拍」既是旅拍又是赠送，只能展示在旅拍行，不在赠送行重复。"""
    p = _parse("产品亮点\n赠送无人机航拍一段，赠送藏装旅拍 6 张。", "A")
    photo = [it.text for it in p.items_of(DIM_PHOTO)]
    gift = [it.text for it in p.items_of(DIM_GIFTS)]
    assert photo, f"旅拍维度应有内容：{photo}"
    assert not gift, f"赠送维度不应再重复展示旅拍条目：{gift}"
    # 展示层（matrix）也不能出现重复
    rows = dict(matrix([p]))
    assert rows[DIM_PHOTO][0]
    assert "无人机" not in rows[DIM_GIFTS][0], rows[DIM_GIFTS]


def test_gift_dim_points_to_photo_when_all_gifts_are_photo():
    """所有赠送项都归于旅拍时，赠送维度不能报「未提及」。"""
    p = _parse("赠送无人机航拍一段，赠送藏装旅拍 6 张。", "A")
    f = p.fact(DIM_GIFTS)
    assert f.status != STATUS_UNKNOWN, f"不应报未提及：{f}"
    assert "旅拍" in f.value, f.value
    assert f.evidence, "缺少原文依据"


def test_pure_gift_still_goes_to_gift_dim():
    """纯赠送（不是旅拍/滑雪）应留在赠送维度，不能被旅拍吃掉。"""
    p = _parse("赠送高原氧气一瓶，赠送藏式伴手礼一份。", "A")
    gift = [it.text for it in p.items_of(DIM_GIFTS)]
    assert len(gift) == 2, gift
    assert all(("氧气" in g) or ("伴手礼" in g) for g in gift), gift


# ---------- 2. 一句话多事实：拆分并分别归类 ----------

def test_one_sentence_split_into_multiple_dims():
    """「赠送旅拍 9 张 + 含 4 小时滑雪体验，正餐自理」应拆成旅拍/滑雪/需自理三条。"""
    p = _parse("费用说明\n赠送旅拍 9 张精修 + 含 4 小时滑雪体验，正餐自理。", "A")
    ski = [it.text for it in p.items_of(DIM_SKIING)]
    photo = [it.text for it in p.items_of(DIM_PHOTO)]
    pay = [it.text for it in p.items_of(DIM_SELF_PAY)]
    assert any("滑雪" in s for s in ski), ski
    assert any("旅拍" in s for s in photo), photo
    assert any("自理" in s for s in pay), pay
    # 三类互不串味
    assert not any("旅拍" in s for s in ski), f"滑雪里混进了旅拍：{ski}"
    assert not any("滑雪" in s for s in photo), f"旅拍里混进了滑雪：{photo}"
    assert not any(("滑雪" in s or "旅拍" in s) for s in pay), f"自理里混进别类：{pay}"


def test_extract_items_returns_separate_units():
    raw = extract_items("赠送藏装旅拍 6 张 + 含 4 小时滑雪体验")
    texts = [it.text for it in raw]
    assert any("旅拍" in t and "滑雪" not in t for t in texts), texts
    assert any("滑雪" in t and "旅拍" not in t for t in texts), texts


# ---------- 3. 「含滑雪体验」不能被判成赠送 ----------

def test_included_skiing_is_not_gift():
    p = _parse("产品亮点\n含 4 小时滑雪体验。", "A")
    assert p.fact(DIM_SKIING).status == STATUS_INCLUDED, p.fact(DIM_SKIING)
    assert p.fact(DIM_GIFTS).status == STATUS_UNKNOWN, p.fact(DIM_GIFTS)
    assert [it.text for it in p.items_of(DIM_GIFTS)] == []
    assert not any("滑雪" in g for g in p.gifts), p.gifts


def test_free_skiing_still_not_gift():
    """「免费提供雪具」属于包含/服务，不是赠送项目。"""
    p = _parse("免费提供雪具一套。", "A")
    assert p.fact(DIM_SKIING).status == STATUS_INCLUDED
    assert not any("雪具" in g for g in p.gifts), p.gifts


# ---------- 4. 明确不包含 ----------

def test_excluded_skiing_recognized():
    p = _parse("费用说明\n滑雪：不含。", "A")
    f = p.fact(DIM_SKIING)
    assert f.status == STATUS_EXCLUDED, f
    assert "不含" in f.value, f.value
    assert "自理" not in f.value, f"不应臆造「自理」：{f.value}"


def test_excluded_goes_to_self_pay_dim_only_when_no_specific_dim():
    """「滑雪：不含」归滑雪维度；与滑雪无关的不含项才落需自理。"""
    p = _parse("滑雪：不含。\n骑马不包含。", "A")
    ski = [it.text for it in p.items_of(DIM_SKIING)]
    pay = [it.text for it in p.items_of(DIM_SELF_PAY)]
    assert any("滑雪" in s for s in ski), ski
    assert any("骑马" in s for s in pay), pay
    assert not any("滑雪" in s for s in pay), f"滑雪不应落进需自理：{pay}"


# ---------- 5. 自费 / 自理识别 ----------

def test_self_pay_and_own_expense_recognized():
    p = _parse("费用说明\n骑马自费。\n正餐自理。", "A")
    pay = [it.text for it in p.items_of(DIM_SELF_PAY)]
    assert len(pay) == 2, pay
    assert any("自费" in s for s in pay), pay
    assert any("自理" in s for s in pay), pay
    assert p.fact(DIM_SELF_PAY).status == STATUS_EXCLUDED
    # 自理与自费并存的混合维度，文案不能只说「需自费」
    assert status_label(p, DIM_SELF_PAY) == "明确需自理/自费", status_label(p, DIM_SELF_PAY)
    # 自理不能混进赠送
    assert not any(("自费" in g or "自理" in g) for g in p.gifts), p.gifts


def test_self_pay_label_distinguishes_own_vs_pay():
    """「自理」（不含、需自行安排）与「自费」（要另外掏钱）口径不同，不能一律写成需自费。"""
    own = _parse("费用说明\n正餐自理。", "A")
    pay = _parse("费用说明\n骑马自费。", "B")
    mix = _parse("费用说明\n晚餐自理，骑马自费。", "C")
    assert status_label(own, DIM_SELF_PAY) == "明确需自理", status_label(own, DIM_SELF_PAY)
    assert status_label(pay, DIM_SELF_PAY) == "明确需自费", status_label(pay, DIM_SELF_PAY)
    assert status_label(mix, DIM_SELF_PAY) == "明确需自理/自费", status_label(mix, DIM_SELF_PAY)


def test_gift_label_is_specific():
    p = _parse("赠送无人机航拍一段。", "A")
    assert status_label(p, DIM_GIFTS) == "明确赠送", status_label(p, DIM_GIFTS)


# ---------- 6. 未提及 ≠ 明确不包含 ----------

def test_unmentioned_not_judged_excluded():
    p = _parse("第一天：成都-康定 住：康定【五钻】\n第二天：康定-成都散团", "A")
    for dim in (DIM_SKIING, DIM_PHOTO, DIM_GIFTS, DIM_SELF_PAY):
        f = p.fact(dim)
        assert f.status == STATUS_UNKNOWN, f"{dim} 应为未提及：{f}"
        assert f.status != STATUS_EXCLUDED


def test_unmentioned_shows_as_unknown_in_matrix():
    a = _parse("含 4 小时滑雪体验。", "A")
    b = _parse("第一天：成都-康定", "B")
    rows = dict(matrix([a, b]))
    assert rows[DIM_SKIING][0] != "未提及"
    assert rows[DIM_SKIING][1] == "未提及"


def test_single_product_mention_does_not_mean_others_excluded():
    """只有 A 写了滑雪，不能推断 B 不包含。"""
    a = _parse("含 4 小时滑雪体验。", "A")
    b = _parse("含藏装旅拍 6 张。", "B")
    assert a.fact(DIM_SKIING).status == STATUS_INCLUDED
    assert b.fact(DIM_SKIING).status == STATUS_UNKNOWN
    assert b.fact(DIM_SKIING).status != STATUS_EXCLUDED


# ---------- 7. 证据不足不标独家 ----------

def test_no_unique_when_evidence_insufficient():
    """A 明确包含滑雪、B 未提及 —— 不能标独家。"""
    a = _parse("含 4 小时滑雪体验。", "A")
    b = _parse("第一天：成都-康定", "B")
    rows = matrix([a, b])
    marks = cell_marks([a, b], rows)
    assert not any(v == "unique" for v in marks.values()), f"证据不足却标了独家：{marks}"


def test_unique_requires_bidirectional_evidence():
    """A 明确包含、B 明确不包含 —— 才算独家。"""
    a = _parse("含 4 小时滑雪体验。", "A")
    b = _parse("滑雪：不含。", "B")
    rows = matrix([a, b])
    marks = cell_marks([a, b], rows)
    ri = [i for i, (n, _) in enumerate(rows) if n == DIM_SKIING][0]
    assert marks.get((ri, 0)) == "unique", marks
    assert marks.get((ri, 1)) is None, marks


# ---------- 8. 原文依据与事实一致 ----------

def test_evidence_matches_extracted_fact():
    p = _parse("费用说明\n滑雪：不含。", "A")
    f = p.fact(DIM_SKIING)
    assert f.evidence, "缺少原文依据"
    assert any(f.value in e or e in f.value for e in f.evidence), (
        f"依据与结论不匹配：{f.value} vs {f.evidence}")


def test_item_evidence_contains_item_text():
    p = _parse("赠送无人机航拍一段，正餐自理，滑雪：不含。", "A")
    assert p.items
    for it in p.items:
        assert it.evidence, f"条目缺依据：{it}"
        core = it.text.rstrip("…")
        assert core in it.evidence or core[:10] in it.evidence, (
            f"依据与条目不一致：{it.text!r} vs {it.evidence!r}")


# ---------- 9. 回归：天数 / 团型 / 用车 / 住宿 / 行程覆盖 ----------

_SAMPLE = (
    "冬日九寨 8 天 7 晚\n"
    "2-8 人小团\n"
    "头等舱商务车\n"
    "第一天：成都-九寨沟 住：九寨沟【五钻】\n"
    "第二天：九寨沟-成都散团\n"
)


def test_regression_duration():
    p = _parse(_SAMPLE, "A")
    assert (p.days, p.nights) == (8, 7), (p.days, p.nights)
    assert p.duration() == "8 天 7 晚", p.duration()


def test_regression_group_and_vehicle():
    p = _parse(_SAMPLE, "A")
    assert "2-8" in p.group_size, p.group_size
    assert p.fact("团型").status == STATUS_INCLUDED
    assert "头等舱" in p.vehicle, p.vehicle
    assert p.fact("用车").status == STATUS_INCLUDED


def test_regression_stays_and_route():
    p = _parse(_SAMPLE, "A")
    assert len(p.stays) == 1, p.stays
    assert p.stays[0].place == "九寨沟", p.stays
    assert p.stays[0].level == "五钻", p.stays
    assert p.route == ["成都", "九寨沟"], p.route


def test_regression_route_no_action_tail():
    """行程节点不应带「集合 / 散团 / 自由活动」这类动作尾巴。"""
    p = _parse("第一天：成都集合-四姑娘山\n第二天：稻城-成都散团", "A")
    assert all(not r.endswith(("集合", "散团", "自由活动", "游玩")) for r in p.route), p.route
    assert p.route == ["成都", "四姑娘山", "稻城"], p.route


# ---------- 10. 费用包含：分隔符不丢条目 ----------

_INCLUDE_VARIANTS = {
    "顿号": "费用包含：车费、住宿 5 晚、门票、早餐。",
    "逗号": "费用包含：车费，住宿 5 晚，门票，早餐。",
    "分号": "费用包含：车费；住宿 5 晚；门票；早餐。",
    "冒号+换行": "费用包含：\n车费\n住宿 5 晚\n门票\n早餐。",
    "换行+顿号": "费用包含：\n车费、住宿 5 晚、门票、早餐。",
    "另起段标题": "行程包含：车费，住宿 5 晚，门票，早餐。",
}


def test_included_items_all_extracted():
    """冒号/顿号/逗号/分号/换行都不能造成条目丢失（「门票」「早餐」是 2 字，最易被漏）。"""
    for name, txt in _INCLUDE_VARIANTS.items():
        p = _parse(txt + "\n滑雪：不含。", "A")
        inc = [it.text for it in p.items_of(DIM_INCLUDED)]
        for kw in ("车费", "住宿", "门票", "早餐"):
            assert any(kw in t for t in inc), f"写法[{name}] 丢失「{kw}」：{inc}"


def test_included_items_not_marked_as_self_pay():
    """费用包含里的项目不能被判成需自理/自费。"""
    p = _parse("费用包含：车费、住宿 5 晚、门票、早餐。\n正餐自理。", "A")
    inc = [it.text for it in p.items_of(DIM_INCLUDED)]
    pay = [it.text for it in p.items_of(DIM_SELF_PAY)]
    assert len(inc) == 4, inc
    assert not any(("门票" in t or "早餐" in t) for t in pay), f"包含项被判成自理：{pay}"


def test_include_context_stops_at_next_section():
    """「费用包含」的继承不能被后面的「滑雪：」「定位：」等段落继续吞掉。"""
    p = _parse("费用包含：车费、门票。\n滑雪：不含。\n定位：蜜月情侣。", "A")
    inc = [it.text for it in p.items_of(DIM_INCLUDED)]
    assert not any("蜜月" in t for t in inc), f"定位被当成包含服务：{inc}"
    assert not any("滑雪" in t for t in inc), f"不含项被当成包含服务：{inc}"


def test_evidence_count_matches_display():
    """展示几条就要有至少几条依据，不能显示 4 项只给 3 条依据。"""
    p = _parse("费用包含：车费、住宿 5 晚、门票、早餐。", "A")
    f = p.fact(DIM_INCLUDED)
    shown = [it.text for it in p.items_of(DIM_INCLUDED)][:4]
    assert len(f.evidence) >= len(shown), f"依据 {len(f.evidence)} 条 < 展示 {len(shown)} 条"


def test_included_items_share_no_mixed_prefix():
    """同一维度里不能出现「费用包含：车费 / 住宿 5 晚」这种前缀参差不齐。"""
    p = _parse("费用包含：车费、住宿 5 晚、门票、早餐。", "A")
    inc = [it.text for it in p.items_of(DIM_INCLUDED)]
    assert not any("费用包含" in t for t in inc), f"仍残留段头前缀：{inc}"
    assert any("车费" in t for t in inc), inc
    # 但原文依据必须保留完整片段，便于人工核实
    assert any("费用包含" in it.evidence for it in p.items_of(DIM_INCLUDED)), (
        [it.evidence for it in p.items_of(DIM_INCLUDED)])


def test_gift_hint_wording_is_dynamic():
    """赠送提示要简洁，且数量来自实际数据而不是写死。"""
    p1 = _parse("赠送无人机航拍一段。", "A")
    assert p1.fact(DIM_GIFTS).value == "共 1 项，详情见「旅拍」维度", p1.fact(DIM_GIFTS).value
    p3 = _parse("赠送无人机航拍一段，赠送藏装旅拍 6 张，赠送底片全送。", "B")
    assert "共 3 项" in p3.fact(DIM_GIFTS).value, p3.fact(DIM_GIFTS).value


# ---------- 11. 展示截断 ----------

def test_stay_summary_clip_has_ellipsis():
    """摘要里的住宿摘要被截断时必须补「…」，且底层 stays 数据保持完整。"""
    from trip_compare.compare import clip_text, summary_lines

    p = _parse(
        "川西 8 天 7 晚\n"
        "第一天：成都 住：成都【五钻】\n第二天：四姑娘山 住：四姑娘山【民宿】\n"
        "第三天：丹巴 住：丹巴【客栈】\n第四天：新都桥 住：新都桥【四钻】\n"
        "第五天：香格里拉镇 住：香格里拉镇【四钻】\n",
        "A")
    full = p.stay_summary()
    assert len(full) > 30, full
    # 底层数据不能被动过
    assert len(p.stays) == 5, p.stays
    assert "香格里拉镇" in full
    clipped = clip_text(full, 30)
    assert clipped.endswith("…"), f"截断未补省略号：{clipped!r}"
    line = [ln for ln in summary_lines([p]) if ln.startswith("住宿")][0]
    assert "…）" in line or "…" in line, line


def test_evidence_has_no_dangling_bracket():
    """原文依据不能出现「（样品数据」这类括号没闭合的残缺片段。"""
    from trip_compare.report import _clip_ev

    p = _parse("川西环线 8 天 7 晚私家团（样品数据，仅供演示）\n独立成团，2 人起订。", "A")
    for dim in ("团型", "行程天数"):
        for e in p.fact(dim).evidence:
            assert "（样品数据" != e[-5:], f"证据被括号截断：{e}"
            assert e.count("（") == e.count("）"), f"括号不配对：{e}"
    # 超长证据的裁剪也要补省略号且不留下未闭合括号
    long_ev = "某产品（这是一段很长的补充说明，用来测试截断是否会留下没有闭合的括号问题" * 2
    clipped = _clip_ev(long_ev)
    assert clipped.endswith("…"), clipped
    assert clipped.count("（") == clipped.count("）"), clipped


# ---------- 12. JSON 字段语义 ----------

def test_self_pay_excludes_plain_excluded_items():
    """「滑雪：不含」是明确不包含，不该混进 self_pay。"""
    p = _parse("滑雪：不含。\n正餐自理。\n骑马自费。", "A")
    assert p.self_pay == ["正餐自理", "骑马自费"], p.self_pay
    assert p.excluded == ["滑雪：不含"], p.excluded


def test_self_pay_and_excluded_json_fields():
    """结构化数据里三种费用语义互不混淆，且旧字段结构保持不变（仍是字符串列表）。"""
    p = _parse("赠送无人机航拍一段。\n费用包含：车费、门票。\n滑雪：不含。\n正餐自理。", "A")
    d = p.to_dict()
    for key in ("gifts", "self_pay", "excluded"):
        assert isinstance(d[key], list), f"{key} 类型变了：{d[key]}"
        assert all(isinstance(x, str) for x in d[key]), d[key]
    assert d["gifts"] == ["赠送无人机航拍一段"]
    assert d["self_pay"] == ["正餐自理"]
    assert d["excluded"] == ["滑雪：不含"]


def test_json_roundtrip_keeps_excluded():
    from trip_compare.schema import TripProduct

    p = _parse("滑雪：不含。\n正餐自理。", "A")
    back = TripProduct.from_dict(p.to_dict())
    assert back.excluded == p.excluded, back.excluded
    assert back.self_pay == p.self_pay, back.self_pay
    assert back.gifts == p.gifts, back.gifts
    # facts 也要能原样往返（状态、结论、依据都不能丢）
    assert set(back.facts) == set(p.facts), set(p.facts) ^ set(back.facts)
    for k, f in p.facts.items():
        assert back.facts[k].status == f.status, (k, back.facts[k], f)
        assert back.facts[k].value == f.value, (k, back.facts[k], f)
        assert back.facts[k].evidence == f.evidence, (k, back.facts[k], f)


def test_included_service_no_unique_when_other_unmentioned():
    """一边写了包含服务、另一边只字未提 —— 不能标独家。"""
    a = _parse("费用包含：门票、早餐。", "A")
    b = _parse("第一天：成都-康定 住：康定【五钻】", "B")
    rows = matrix([a, b])
    marks = cell_marks([a, b], rows)
    assert not any(v == "unique" for v in marks.values()), f"证据不足却标独家：{marks}"


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
        except Exception as e:  # noqa: BLE001
            failed += 1
            print(f"  ERROR {fn.__name__}: {type(e).__name__}: {e}")
    print(f"\n{len(fns) - failed}/{len(fns)} passed")
    sys.exit(1 if failed else 0)
