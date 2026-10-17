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
    CAT_EXCLUDED,
    CAT_GIFT,
    CAT_INCLUDED,
    CAT_PHOTO,
    CAT_SELF_PAY,
    CAT_SKIING,
    STATUS_AMBIGUOUS,
    STATUS_EXCLUDED,
    STATUS_INCLUDED,
    STATUS_UNKNOWN,
    ExtractedItem,
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
DIM_INCLUDED = "包含服务"
DIM_DURATION = "行程天数"
DIM_STAYS = "住宿配置"
DIM_ROUTE = "行程覆盖"

# ---------- 语义分类模式 ----------
# 明确不包含（写了「不含」）
_EXCLUDED_RE = re.compile(r"不含|不包含|未含|不赠送|不提供|没有|无赠送")
# 需自理/自费（要另外掏钱）
_SELF_PAY_RE = re.compile(r"自理|自费|需另付|另行付费|需自理|费用自理|自行购买")
# 包含（含在费用里，但不是赠送）
_INCLUDED_RE = re.compile(r"含|包含|免费|提供|已含|赠送|含票|含用车|含住宿")


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


# 括号配对：切分子句时不能把「（样品数据，仅供演示）」从中间劈开
_BRACKET_PAIR = {"（": "）", "(": ")", "【": "】", "[": "]", "《": "》", "<": ">"}


def _unclosed_count(s: str) -> int:
    """开启括号数 - 闭合括号数；>0 表示这段里有未闭合的括号。"""
    return sum(s.count(o) for o in _BRACKET_PAIR) - sum(s.count(c) for c in _BRACKET_PAIR.values())


def _merge_unclosed(parts: list[str]) -> list[str]:
    """把落在括号内被切开的子句合并回去，避免产出「川西环线 8 天…（样品数据」这类残缺片段。"""
    out = list(parts)
    for _ in range(5):
        merged: list[str] = []
        for p in out:
            if merged and _unclosed_count(merged[-1]) > 0:
                merged[-1] = merged[-1] + "，" + p
            else:
                merged.append(p)
        if merged == out:
            break
        out = merged
    return out


def _subclauses(s: str) -> list[str]:
    """把一句话按逗号/顿号切成子句——同一句常同时含「含 X」和「X 自理」。"""
    parts = [c.strip() for c in re.split(r"[，,、]+", s)]
    parts = [c for c in parts if len(c) >= 2] or [s]
    return _merge_unclosed(parts)


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


# 「费用包含：」这类段头：冒号后可能直接跟内容，也可能换行另起、用分号另起
_INCLUDE_HEAD_RE = re.compile(
    r"(?:费用包含|费用已含|费用包含项目|(?<![不未无])包含|(?<![不未无])含)\s*[:：]"
)
# 新的段落标题（如「定位：」「滑雪：」）——出现即表示上一段结束
_TITLE_HEAD_RE = re.compile(r"^[^：:]{1,10}[：:]")
# 只有段头、没有内容的行（如单独一行「费用包含：」）——不算一条事实
_HEAD_ONLY_RE = re.compile(r"^\s*(?:费用包含|费用已含|费用包含项目|包含|含)\s*[:：]\s*$")


def _facts_split(sent: str) -> list[str]:
    """把一句话切成更小的「事实单元」。

    先按逗号/顿号切；如果一个单元里同时出现滑雪类和旅拍类关键词
    （典型如「赠送旅拍 X 张 + 含 4 小时滑雪体验」），再按 + 号细切，
    避免把两件事当成一件事归到同一个字段。
    """
    parts = [p.strip() for p in re.split(r"[，,、]+", sent)]
    parts = [p for p in parts if len(p) >= 2] or [sent]
    parts = _merge_unclosed(parts)
    out: list[str] = []
    for p in parts:
        if _SKI_KW.search(p) and _PHOTO_KW.search(p):
            sub = [x.strip() for x in re.split(r"\s*[+＋]\s*|；", p) if len(x.strip()) >= 2]
            out.extend(sub or [p])
        else:
            out.append(p)
    return out


def _classify(c: str) -> tuple[list[str], str] | None:
    """判定一个事实单元的类别与状态。返回 (categories, status)，无法归类返回 None。"""
    excl = _EXCLUDED_RE.search(c)
    pay = _SELF_PAY_RE.search(c)
    gift = _GIFT_KW.search(c)
    pos = _INCLUDED_RE.search(c)

    cats: list[str] = []
    if _SKI_KW.search(c):
        cats.append(CAT_SKIING)
    if _PHOTO_KW.search(c):
        cats.append(CAT_PHOTO)

    # 费用语义互斥：赠送 > 自费 > 明确不含 > 包含
    if gift and not (excl or pay):
        cats.append(CAT_GIFT)
    elif pay:
        cats.append(CAT_SELF_PAY)
    elif excl:
        cats.append(CAT_EXCLUDED)
    elif pos:
        cats.append(CAT_INCLUDED)

    if not cats:
        return None

    if CAT_GIFT in cats or CAT_INCLUDED in cats:
        status = STATUS_INCLUDED
    elif CAT_SELF_PAY in cats or CAT_EXCLUDED in cats:
        status = STATUS_EXCLUDED
    else:
        # 只提到关键词（如地名「滑雪场」），没有肯定也没有否定表述
        status = STATUS_AMBIGUOUS
    return cats, status


def extract_items(text: str) -> list[ExtractedItem]:
    """从全文切出独立事实条目并分类。一条事实 = 一件事。"""
    out: list[ExtractedItem] = []
    # 「费用包含」的语境可以跨句延续：分项可能用顿号、逗号、分号分隔，也可能换行另起。
    # 一旦出现新的段落标题、行程日行，或出现赠送/自理/不含这类新费用语义，继承即终止。
    pending_include = False
    for s in _sentences(text):
        day_line = bool(_DAY_HEAD_LINE.match(s))
        head_m = _INCLUDE_HEAD_RE.search(s)
        if head_m:
            pending_include = True
        elif day_line or _TITLE_HEAD_RE.match(s):
            pending_include = False
        inherit_include = pending_include
        for c in _facts_split(s):
            c = re.sub(r"^[◆✦✅►▶\-\s]+", "", c).strip().rstrip("。；;，,、")
            if _HEAD_ONLY_RE.match(c):
                continue  # 「费用包含：」这种空段头不是事实
            # 处于费用包含语境时允许 2 字条目（「门票」「早餐」），否则 2 字多为噪音
            min_len = 2 if inherit_include else 3
            if len(c) < min_len or len(c) > MAX_LINE:
                continue
            if _GENERIC_GIFT.search(c):
                continue  # 「此为赠送项目」这类没有信息量的说明
            if day_line and not (
                _GIFT_KW.search(c) or _SELF_PAY_RE.search(c)
                or _EXCLUDED_RE.search(c) or _INCLUDED_RE.search(c)
            ):
                continue  # 行程日行里只保留带费用语义的片段，避免把途经点当项目
            r = _classify(c)
            if r:
                # 进入新的费用语义（赠送/自理/不含），「费用包含」的继承到此为止
                if any(cat in r[0] for cat in (CAT_GIFT, CAT_SELF_PAY, CAT_EXCLUDED)):
                    pending_include = False
            else:
                if inherit_include and not (_EXCLUDED_RE.search(c) or _SELF_PAY_RE.search(c)):
                    r = ([CAT_INCLUDED], STATUS_INCLUDED)  # 继承「费用包含」语境
                else:
                    continue
            cats, status = r
            # 展示只留项目本身（车费），但原文依据保留完整片段（费用包含：车费），
            # 避免同一维度里出现「费用包含：车费 / 住宿 5 晚」前缀参差不齐的情况
            raw = c
            hm = _INCLUDE_HEAD_RE.match(c)
            if hm and len(c[hm.end():].strip()) >= 2:
                c = c[hm.end():].strip()
            out.append(ExtractedItem(
                text=_clip(c, 50),
                categories=cats,
                status=status,
                evidence=_clip(raw, 60),
            ))
    return _dedupe_items(out)


def _dedupe_items(items: list[ExtractedItem]) -> list[ExtractedItem]:
    """按「归一化后互相包含」去重，保留先出现的、信息更全的那条。"""
    out: list[ExtractedItem] = []
    for it in items:
        na = _norm(it.text)
        if any(na != _norm(o.text) and (na in _norm(o.text) or _norm(o.text) in na)
               and set(it.categories) & set(o.categories)
               for o in out):
            continue
        if any(na == _norm(o.text) and it.categories == o.categories for o in out):
            continue
        out.append(it)
    return out


def items_of(items: list[ExtractedItem], cat: str) -> list[ExtractedItem]:
    """取「主要归属」为某类别的条目（按 CAT_PRIORITY 唯一归属）。

    这样「赠送无人机航拍」只算旅拍条目，不会再在赠送项目里重复出现一次。
    """
    from .schema import CAT_PRIORITY

    out = []
    for it in items:
        primary = next((c for c in CAT_PRIORITY if it.has(c)), None)
        if primary == cat:
            out.append(it)
    return out


def _gift_fact(all_items: list[ExtractedItem], gift_items: list[ExtractedItem]) -> Fact:
    """赠送项目维度。

    若所有赠送项都同时属于滑雪/旅拍（已在那两行展示），这里不能报「未提及」——
    那会让人误以为没有赠送。改为指向对应维度。
    """
    from .schema import CAT_PRIORITY

    from .compare import DIM_OF_CAT

    if gift_items:
        return fact_from_items(gift_items)
    gifts_elsewhere = [it for it in all_items if it.has(CAT_GIFT)]
    if not gifts_elsewhere:
        return Fact(status=STATUS_UNKNOWN)
    dims: list[str] = []
    for it in gifts_elsewhere:
        primary = next((c for c in CAT_PRIORITY if it.has(c)), None)
        d = DIM_OF_CAT.get(primary or "", "")
        if d and d not in dims:
            dims.append(d)
    return Fact(
        status=STATUS_INCLUDED,
        value=f"共 {len(gifts_elsewhere)} 项，详情见「{'、'.join(dims)}」维度",
        evidence=[it.evidence for it in gifts_elsewhere[:3]],
    )


def fact_from_items(items: list[ExtractedItem]) -> Fact:
    """把同一维度的事实条目聚合成 Fact：状态一致才敢下结论。"""
    if not items:
        return Fact(status=STATUS_UNKNOWN)
    statuses = {it.status for it in items}
    if len(statuses) == 1:
        status = next(iter(statuses))
    else:
        status = STATUS_AMBIGUOUS  # 同一维度内说法不一致，交人工确认
    from .compare import MAX_SHOW

    n = MAX_SHOW
    value = "；".join(_clip(it.text, 32) for it in items[:n])
    if len(items) > n:
        value += f"（共 {len(items)} 条）"
    return Fact(status=status, value=value,
                evidence=[it.evidence for it in items[:n]])


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
            part = re.sub(r"(集合|散团|一日游|半日游|自由活动|游玩)$", "", part)  # 去掉动作尾巴
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

def _duration_text(days: int | None, nights: int | None) -> str:
    if days and nights:
        return f"{days} 天 {nights} 晚"
    return f"{days} 天" if days else "—"


def _stay_text(stays: list[Stay]) -> str:
    parts: list[str] = []
    for s in stays:
        txt = (s.place + " " + s.level).strip()
        if s.note:
            txt += f"（{s.note}）"
        parts.append(txt or "—")
    return "；".join(parts)


def parse(doc: Doc) -> TripProduct:
    text = doc.text
    days, nights = extract_duration(text)
    sents = _sentences(text)

    # 1) 先把全文切成独立事实并分类（去重、互斥都在这层完成）
    items = extract_items(text)
    route = extract_route(text)
    stays = extract_stays(text)

    ski_items = items_of(items, CAT_SKIING)
    photo_items = items_of(items, CAT_PHOTO)
    gift_items = items_of(items, CAT_GIFT)
    pay_items = items_of(items, CAT_SELF_PAY) + items_of(items, CAT_EXCLUDED)
    incl_items = items_of(items, CAT_INCLUDED)

    # 2) 派生维度（天数 / 住宿 / 行程覆盖）也建立 Fact：
    #    它们有确定取值，不能因为没有 Fact 而在报告里显示成「未提及」
    f_duration = Fact(status=STATUS_UNKNOWN)
    if days:
        ev = [_clip(s, 40) for s in sents
              if _RE_DAYS_NIGHTS.search(s) or _RE_DAYS_ONLY.search(s)][:2]
        f_duration = Fact(status=STATUS_INCLUDED, value=_duration_text(days, nights), evidence=ev)

    f_stays = Fact(status=STATUS_UNKNOWN)
    if stays:
        f_stays = Fact(
            status=STATUS_INCLUDED,
            value=_clip(_stay_text(stays), 80),
            evidence=[_clip(ln, 40) for ln in _lines(text) if _RE_STAY_LINE.search(ln)][:4],
        )

    f_route = Fact(status=STATUS_UNKNOWN)
    if route:
        f_route = Fact(
            status=STATUS_INCLUDED,
            value=" → ".join(route[:10]),
            evidence=[_clip(ln, 40) for ln in _lines(text) if _RE_DAY_HEAD.match(ln)][:4],
        )

    # 3) 各维度聚合为 Fact（状态不一致 => ambiguous）
    f_ski = fact_from_items(ski_items)
    f_photo = fact_from_items(photo_items)
    f_gifts = _gift_fact(items, gift_items)
    f_self_pay = fact_from_items(pay_items)
    f_included = fact_from_items(incl_items)
    f_vehicle = fact_vehicle(text, sents)
    f_group = fact_group_size(text, sents)
    f_audience = fact_audience(text, sents)

    facts = {
        DIM_VEHICLE: f_vehicle,
        DIM_GROUP: f_group,
        DIM_SKIING: f_ski,
        DIM_PHOTO: f_photo,
        DIM_AUDIENCE: f_audience,
        DIM_GIFTS: f_gifts,
        DIM_SELF_PAY: f_self_pay,
        DIM_INCLUDED: f_included,
        DIM_DURATION: f_duration,
        DIM_STAYS: f_stays,
        DIM_ROUTE: f_route,
    }

    # 4) 兼容旧字段：保留该类事实的全量（结构化数据里不丢信息），
    #    展示层的去重由 items_of(dim) 负责——一条事实只在最具体的维度出现一次。
    # 三种费用语义分开存：赠送 / 需自理或自费 / 明确不包含（如「滑雪：不含」）。
    # 旧字段 self_pay 只保留「需自理/自费」，明确不包含单列到 excluded，避免语义混淆。
    gifts = [it.text for it in items if it.has(CAT_GIFT)]
    self_pay = [it.text for it in items if it.has(CAT_SELF_PAY)]
    excluded = [it.text for it in items if it.has(CAT_EXCLUDED)]

    return TripProduct(
        code=extract_code(doc),
        title=extract_title(doc),
        days=days,
        nights=nights,
        group_size=extract_group_size(text),
        vehicle=extract_vehicle(text),
        route=route,
        stays=stays,
        gifts=gifts,
        self_pay=self_pay,
        excluded=excluded,
        # 字符串字段只保留「有把握的结论」，unknown 时留空，状态看 facts
        skiing=f_ski.value if f_ski.status != STATUS_UNKNOWN else "",
        photography=f_photo.value if f_photo.status != STATUS_UNKNOWN else "",
        audience=extract_audience(text),
        source_file=doc.name,
        extractor="rules",
        facts=facts,
        items=items,
    )
