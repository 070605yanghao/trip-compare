# -*- coding: utf-8 -*-
"""规则解析引擎：从旅游产品说明书（PDF/文本）提取结构化字段。

设计原则：
- 只提取「确定性高」的字段，提不到就留空，交给上层（可选 LLM）兜底；
- 所有规则基于中文旅游行业文案的常见写法，按关键词锚定；
- 每个字段独立提取，互不依赖，失败不影响其他字段。
"""
from __future__ import annotations

import re

from .extract import Doc
from .schema import (
    STATUS_AMBIGUOUS,
    STATUS_EXCLUDED,
    STATUS_INCLUDED,
    STATUS_UNKNOWN,
    Fact,
    Stay,
    TripProduct,
)

# ---------- 常量 ----------

MAX_LINE = 80

_RE_DAYS_NIGHTS = re.compile(r"(\d{1,2})\s*天\s*(\d{1,2})\s*晚")
_RE_DAYS_ONLY = re.compile(r"(?<![\d\-—~.])(\d{1,2})\s*日(?!\s*(夜|期|常|程|历))")
_RE_GROUP = re.compile(r"(\d{1,2}\s*[-–—~]\s*\d{1,2})\s*人\s*(?:拼车|小团|mini|MINI|团)")
_RE_GROUP_MIN = re.compile(r"(\d{1,2})\s*人\s*起订")
_RE_DAY_HEAD = re.compile(
    r"(?:DAY\s*\d+|D\s*\d+|第[一二三四五六七八九十]+天)\s*[|｜:：]?\s*(.+)"
)
_RE_STAY_LINE = re.compile(r"住\s*[:：]?\s*([^\n【]{1,20})【([^】]{1,20})】")
_RE_HOTEL_LINE = re.compile(r"参考酒店[:：]\s*(.+)")
_RE_LEVEL = re.compile(r"[一二三四五5５]\s*钻|钻级|木屋|营地|民宿|客栈|山庄")

_GIFT_KW = re.compile(r"赠送|赠[:：]|赠\s|伴手礼|欢迎礼|免费赠")
_SELF_PAY_KW = re.compile(r"自理|自费|需另付|另行付费|不含|不包含|未含|不赠送")
_VEHICLE_KW = re.compile(r"头等舱|福特\s*T8|商务车|越野车|SUV|GL8|座车|车型")
_SKI_KW = re.compile(r"滑雪|雪票|雪具")
_PHOTO_KW = re.compile(r"旅拍|航拍|无人机|单反|精修|跟车视频|底片")
_AUDIENCE_KW = re.compile(r"蜜月|亲子|闺蜜|单人|家庭|情侣|毕业")
_NOISE_STOP = re.compile(r"[（(【\[<][^）)】\]>]*[）)】\]>]")  # 去掉途经点里的括号注释

# ---------- 肯定 / 否定模式（用于判定「包含」还是「不包含」） ----------
# 通用否定：命中即视为「明确不包含」（含「不含/自理/自费/需另付」等）
_NEG_ANY = re.compile(r"不含|不包含|未含|自理|自费|需另付|另行付费|不赠送|需自理")
# 通用肯定
_POS_ANY = re.compile(r"含|包含|赠送|免费|提供|已含|送")

# 滑雪
_SKI_POS = re.compile(
    r"(?:含|包含|赠送|免费|已含|提供)[^，。；]{0,8}(?:滑雪|雪票|雪具)"
    r"|(?:滑雪|雪票)[^，。；]{0,8}(?:含|包含|赠送|免费)"
    r"|\d+\s*(?:小时|H|h|天)[^，。；]{0,4}滑雪"
)
# 注意：否定词不能用单独的「无」——「无人机航拍」里的「无」会造成误判
_SKI_NEG = re.compile(
    r"(?:不含|不包含|未含|没有)[^，。；]{0,6}(?:滑雪|雪票|雪具)"
    r"|(?:滑雪|雪票|雪具)[^，。；]{0,6}(?:自理|自费|不含|需另付|另行付费)"
)
# 旅拍
_PHOTO_POS = re.compile(
    r"(?:含|包含|赠送|免费|送|已含|提供)[^，。；]{0,8}(?:旅拍|航拍|无人机|精修|底片|跟车视频|单反)"
    r"|(?:旅拍|航拍|无人机|精修|跟车视频)[^，。；]{0,8}(?:含|包含|赠送|送)"
    r"|\d+\s*张[^，。；]{0,6}(?:精修|旅拍|照片|底片)"
)
_PHOTO_NEG = re.compile(
    r"(?:不含|不包含|未含|没有)[^，。；]{0,6}(?:旅拍|航拍|无人机|精修|跟车视频)"
    r"|(?:旅拍|航拍|无人机|精修|跟车视频)[^，。；]{0,6}(?:自理|自费|不含|需另付|另行付费)"
)

# 维度名（与对比矩阵行名一致，report 用它取状态）
DIM_VEHICLE = "用车"
DIM_GROUP = "团型"
DIM_SKIING = "滑雪"
DIM_PHOTO = "旅拍"
DIM_AUDIENCE = "定位人群"
DIM_GIFTS = "赠送项目"
DIM_SELF_PAY = "需自理"


# ---------- 小工具 ----------

def _lines(text: str) -> list[str]:
    return [ln.strip() for ln in text.splitlines() if ln.strip()]


def _first(text: str, pattern: re.Pattern) -> str:
    m = pattern.search(text)
    return m.group(0).strip() if m else ""


def _dedupe(items: list[str]) -> list[str]:
    seen, out = set(), []
    for it in items:
        it = it.strip()
        if it and it not in seen:
            seen.add(it)
            out.append(it)
    return out


def _clip(s: str, n: int = 60) -> str:
    s = s.strip()
    return s if len(s) <= n else s[: n - 1] + "…"


def _sentences(text: str) -> list[str]:
    """按行 → 按句号/分号切句，保留原文片段（用于 evidence）。"""
    out: list[str] = []
    for ln in _lines(text):
        for s in re.split(r"[。；;！!？?]+", ln):
            s = s.strip().strip("-◆✦✅►▶*·—=＝ ")
            if len(s) >= 2:
                out.append(s)
    return out


def _subclauses(s: str) -> list[str]:
    """把一句话按逗号/顿号切成子句——同一句常同时含「含 X」和「X 自理」。"""
    parts = [c.strip() for c in re.split(r"[，,、]+", s)]
    return [c for c in parts if len(c) >= 2] or [s]


def _dedupe_subseq(items: list[str]) -> list[str]:
    """去重，并丢弃被更长条目包含的短条目（避免「赠送旅拍」和「赠送旅拍 9 张」重复）。"""
    uniq = _dedupe(items)
    return [a for a in uniq if not any(a != b and a in b for b in uniq)]


def _norm(s: str) -> str:
    """归一化：去掉空白与标点，用于判断两条是不是同一件事。"""
    return re.sub(r"[\s，,、。;；:：（）()【】\[\]<>《》“”\"'·\-—]+", "", s or "")


def _dedupe_norm(items: list[str]) -> list[str]:
    """在 _dedupe_subseq 基础上，再合并「去掉标点空白后互相包含」的近似重复。"""
    base = _dedupe_subseq(items)
    out: list[str] = []
    for a in base:
        na = _norm(a)
        if any(na != _norm(b) and (na in _norm(b) or _norm(b) in na) for b in out):
            continue
        out.append(a)
    return out


_DAY_HEAD_LINE = re.compile(r"^(?:DAY\s*\d+|D\s*\d+|第[一二三四五六七八九十]+天)")
# 无信息量的泛化说明句：只说「这是赠送项目」，没说送什么
_GENERIC_GIFT = re.compile(
    r"^(?:此|本|该)[^，。；]{0,12}赠送(?:项目|体验项目)?$"
    r"|赠送项目(?:不去|不参加)?(?:则)?不退"
    r"|^赠送项目$"
)


def _build_fact(
    sents: list[str],
    kw: re.Pattern,
    pos: re.Pattern,
    neg: re.Pattern,
    key: str = "",
) -> Fact:
    """通用判定：先找含关键词的原文，再按肯定/否定模式定状态。

    关键：pos 判定要排除同时含 neg 的子句（「不含滑雪」里的「含」不算肯定）。
    """
    hits = [s for s in sents if kw.search(s)]
    if not hits:
        return Fact(status=STATUS_UNKNOWN)

    subs: list[str] = []
    for s in hits:
        subs.extend(_subclauses(s))
    subs = [c for c in subs if kw.search(c)]
    if not subs:
        subs = hits

    neg_hits = [c for c in subs if neg.search(c)]
    pos_hits = [c for c in subs if pos.search(c) and not neg.search(c)]

    # 证据排序：带肯定/否定标记的子句更能支撑结论，排在前面
    ranked = sorted(
        _dedupe(subs),
        key=lambda c: (0 if (pos.search(c) or neg.search(c)) else 1, len(c)),
    )
    ev = [_clip(c, 60) for c in ranked[:3]]
    if pos_hits and neg_hits:
        # 同时出现「含 X」和「X 自理」——自相矛盾，标为模糊而不是二选一
        return Fact(
            status=STATUS_AMBIGUOUS,
            value="部分包含：" + _clip(pos_hits[0], 40) + "｜" + _clip(neg_hits[0], 40),
            evidence=ev,
        )
    if pos_hits:
        return Fact(status=STATUS_INCLUDED, value=_clip(pos_hits[0], 60), evidence=ev)
    if neg_hits:
        return Fact(status=STATUS_EXCLUDED, value=_clip(neg_hits[0], 60), evidence=ev)
    # 提到了关键词，但既没有肯定也没有否定表述（如只出现地名「滑雪场」）
    return Fact(status=STATUS_AMBIGUOUS, value=_clip(subs[0], 60), evidence=ev)


# ---------- 字段提取 ----------

def extract_code(doc: Doc) -> str:
    m = re.match(r"([A-Za-z]{0,3}-?\d+[A-Za-z-]*)", doc.name)
    return m.group(1) if m else ""


def extract_title(doc: Doc) -> str:
    day_head = re.compile(r"^(DAY\s*\d+|D\s*\d+|第[一二三四五六七八九十]+天)")
    for ln in _lines(doc.text)[:200]:
        ln = ln.strip("=＝-*·— \t")
        if not ln or day_head.match(ln):
            continue  # 行程日行（第一天：...）不是标题
        if 6 <= len(ln) <= 40 and re.search(r"天|日", ln) and "住" not in ln[:6]:
            return _clip(ln, 40)
    return doc.name


def extract_duration(text: str) -> tuple[int | None, int | None]:
    m = _RE_DAYS_NIGHTS.search(text)
    if m:
        return int(m.group(1)), int(m.group(2))
    m = _RE_DAYS_ONLY.search(text[:3000])
    if m:
        d = int(m.group(1))
        return d, d - 1
    return None, None


def extract_group_size(text: str) -> str:
    m = _RE_GROUP.search(text)
    if m:
        return re.sub(r"\s+", "", m.group(1)) + " 人小团"
    m = _RE_GROUP_MIN.search(text)
    if m:
        return m.group(1) + " 人起订"
    return ""


def extract_vehicle(text: str) -> str:
    for ln in _lines(text):
        if _VEHICLE_KW.search(ln) and len(ln) <= 60 and not ln.startswith(("◆", "▶")):
            return _clip(ln)
    return ""


def extract_route(text: str) -> list[str]:
    stops: list[str] = []
    for ln in _lines(text):
        m = _RE_DAY_HEAD.match(ln)
        if not m:
            continue
        seg = m.group(1)
        for part in re.split(r"[-—→>]|·", seg):
            part = _NOISE_STOP.sub("", part).strip(" ，,。;；/\\")
            part = re.sub(r"\s*住[:：].*$", "", part)      # 去掉「住：XX」尾巴
            part = re.sub(r"\s*用餐[:：].*$", "", part)    # 去掉「用餐：...」尾巴
            part = re.sub(r"^[^\u4e00-\u9fa5A-Za-z0-9]+|[^\u4e00-\u9fa5A-Za-z0-9]+$", "", part)
            if 2 <= len(part) <= 18:
                stops.append(part)
    return _dedupe(stops)[:14]


def extract_stays(text: str) -> list[Stay]:
    stays: list[Stay] = []
    raw = _lines(text)
    # 有的说明书把「住：」和住宿内容分成两行，先合并
    lines: list[str] = []
    i = 0
    while i < len(raw):
        ln = raw[i]
        if ln.rstrip().endswith(("住：", "住:")) and i + 1 < len(raw):
            ln = ln + raw[i + 1]
            i += 1
        lines.append(ln)
        i += 1
    for ln in lines:
        for m in _RE_STAY_LINE.finditer(ln):
            place, level = m.group(1).strip(), m.group(2).strip()
            if place and not place.startswith(("用餐", "行程")):
                stays.append(Stay(place=_clip(place, 20), level=_clip(level, 20)))
        m = _RE_HOTEL_LINE.search(ln)
        if m and len(stays) < 20:
            note = m.group(1)
            if _RE_LEVEL.search(note):
                stays.append(Stay(place="", level="", note=_clip(note, 40)))
    # 去重（同 place+level）
    seen, out = set(), []
    for s in stays:
        key = (s.place, s.level)
        if key not in seen:
            seen.add(key)
            out.append(s)
    return out[:12]


def extract_gifts(text: str) -> list[str]:
    """赠送项：按子句判定，且只收「明确是赠送」的子句。

    关键修正：含否定词的子句（如「雪票自理」）不再混入赠送项。
    """
    gifts: list[str] = []
    for s in _sentences(text):
        if _DAY_HEAD_LINE.match(s):
            continue  # 行程日行（DAY3|...）不是赠送项说明
        for c in _subclauses(s):
            c = re.sub(r"^[◆✦✅►▶\-\s]+", "", c)
            if _GENERIC_GIFT.search(c):
                continue
            if _GIFT_KW.search(c) and not _NEG_ANY.search(c) and 3 <= len(c) <= MAX_LINE:
                gifts.append(_clip(c, 50))
    return _dedupe_norm(gifts)[:15]


def extract_self_pay(text: str) -> list[str]:
    """需自理：含「自理/自费/不含/需另付」的子句。"""
    items: list[str] = []
    for s in _sentences(text):
        for c in _subclauses(s):
            if _SELF_PAY_KW.search(c) and 3 <= len(c) <= 50:
                items.append(_clip(re.sub(r"^[◆✦✅►▶\-\s]+", "", c), 40))
    return _dedupe_subseq(items)[:10]


def fact_skiing(text: str, sents: list[str] | None = None) -> Fact:
    return _build_fact(sents or _sentences(text), _SKI_KW, _SKI_POS, _SKI_NEG)


def fact_photography(text: str, sents: list[str] | None = None) -> Fact:
    return _build_fact(sents or _sentences(text), _PHOTO_KW, _PHOTO_POS, _PHOTO_NEG)


def _build_desc_fact(sents: list[str], kw: re.Pattern) -> Fact:
    """描述型字段（用车/团型/人群）：说明书里写明即是事实，无需「含」字佐证。

    只有出现否定表述（自理/不含/自费）才算「明确不包含」。
    """
    hits = [s for s in sents if kw.search(s)]
    if not hits:
        return Fact(status=STATUS_UNKNOWN)
    subs: list[str] = []
    for s in hits:
        subs.extend(_subclauses(s))
    subs = [c for c in subs if kw.search(c)] or hits
    neg_hits = [c for c in subs if _NEG_ANY.search(c)]
    # 候选排序：优先取描述本身（「独立成团」），而不是顺带提到它的标题行（含「8 天 7 晚」）
    pos_hits = sorted(
        [c for c in subs if not _NEG_ANY.search(c)],
        key=lambda c: (1 if re.search(r"\d+\s*[天晚日]|样品数据|仅供演示", c) else 0, len(c)),
    )
    ev = [_clip(c, 60) for c in _dedupe(pos_hits or subs)[:3]]
    if neg_hits and pos_hits:
        return Fact(status=STATUS_AMBIGUOUS,
                    value=_clip(pos_hits[0], 40) + "｜" + _clip(neg_hits[0], 40),
                    evidence=ev)
    if neg_hits:
        return Fact(status=STATUS_EXCLUDED, value=_clip(neg_hits[0], 60), evidence=ev)
    return Fact(status=STATUS_INCLUDED, value=_clip(pos_hits[0], 60), evidence=ev)


def fact_vehicle(text: str, sents: list[str] | None = None) -> Fact:
    return _build_desc_fact(sents or _sentences(text), _VEHICLE_KW)


def fact_group_size(text: str, sents: list[str] | None = None) -> Fact:
    kw = re.compile(r"\d{1,2}\s*[-–—~]\s*\d{1,2}\s*人|\d{1,2}\s*人\s*(?:起订|成团|小团|拼车)|独立成团|私家团")
    return _build_desc_fact(sents or _sentences(text), kw)


def fact_audience(text: str, sents: list[str] | None = None) -> Fact:
    return _build_desc_fact(sents or _sentences(text), _AUDIENCE_KW)


def fact_list(items: list[str], kw: re.Pattern, sents: list[str]) -> Fact:
    """列表型字段（赠送/自理）的状态：有明确条目 = 包含；完全没有提及 = 未提及。"""
    if items:
        return Fact(
            status=STATUS_INCLUDED,
            value="；".join(items[:4]),
            evidence=[_clip(s, 60) for s in sents if kw.search(s)][:3],
        )
    if any(kw.search(s) for s in sents):
        return Fact(status=STATUS_AMBIGUOUS, value="原文提及但未能定位具体条目")
    return Fact(status=STATUS_UNKNOWN)


def extract_audience(text: str) -> str:
    m = _AUDIENCE_KW.search(text)
    return m.group(0) if m else ""


# ---------- 入口 ----------

def parse(doc: Doc) -> TripProduct:
    text = doc.text
    days, nights = extract_duration(text)
    sents = _sentences(text)

    gifts = extract_gifts(text)
    self_pay = extract_self_pay(text)

    f_ski = fact_skiing(text, sents)
    f_photo = fact_photography(text, sents)
    f_vehicle = fact_vehicle(text, sents)
    f_group = fact_group_size(text, sents)
    f_audience = fact_audience(text, sents)
    f_gifts = fact_list(gifts, _GIFT_KW, sents)
    f_self_pay = fact_list(self_pay, _SELF_PAY_KW, sents)

    facts = {
        DIM_VEHICLE: f_vehicle,
        DIM_GROUP: f_group,
        DIM_SKIING: f_ski,
        DIM_PHOTO: f_photo,
        DIM_AUDIENCE: f_audience,
        DIM_GIFTS: f_gifts,
        DIM_SELF_PAY: f_self_pay,
    }

    return TripProduct(
        code=extract_code(doc),
        title=extract_title(doc),
        days=days,
        nights=nights,
        group_size=extract_group_size(text),
        vehicle=extract_vehicle(text),
        route=extract_route(text),
        stays=extract_stays(text),
        gifts=gifts,
        self_pay=self_pay,
        # 字符串字段只保留「有把握的结论」，unknown 时留空，状态看 facts
        skiing=f_ski.value if f_ski.status != STATUS_UNKNOWN else "",
        photography=f_photo.value if f_photo.status != STATUS_UNKNOWN else "",
        audience=extract_audience(text),
        source_file=doc.name,
        extractor="rules",
        facts=facts,
    )
