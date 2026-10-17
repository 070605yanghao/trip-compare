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
from .schema import Stay, TripProduct

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

_GIFT_KW = re.compile(r"赠送|赠[:：]|赠\s")
_SELF_PAY_KW = re.compile(r"自理|自费")
_VEHICLE_KW = re.compile(r"头等舱|福特\s*T8|商务车|越野车|SUV|GL8|座车|车型")
_SKI_KW = re.compile(r"滑雪")
_PHOTO_KW = re.compile(r"旅拍|航拍|无人机|单反|精修|跟车视频")
_AUDIENCE_KW = re.compile(r"蜜月|亲子|闺蜜|单人|家庭|情侣|毕业")
_NOISE_STOP = re.compile(r"[（(【\[<][^）)】\]>]*[）)】\]>]")  # 去掉途经点里的括号注释


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
    gifts: list[str] = []
    for ln in _lines(text):
        if _GIFT_KW.search(ln) and 4 <= len(ln) <= MAX_LINE:
            gifts.append(_clip(re.sub(r"^[◆✦✅►▶\-\s]+", "", ln)))
    return _dedupe(gifts)[:15]


def extract_self_pay(text: str) -> list[str]:
    items: list[str] = []
    for ln in _lines(text):
        if _SELF_PAY_KW.search(ln) and 4 <= len(ln) <= 50:
            items.append(_clip(re.sub(r"^[◆✦✅►▶\-\s]+", "", ln), 40))
    return _dedupe(items)[:10]


def extract_skiing(text: str) -> str:
    hits = [ln for ln in _lines(text) if _SKI_KW.search(ln)]
    if not hits:
        return ""
    for ln in hits:
        if re.search(r"含.*雪票|赠送.*滑雪|含\s*\d+\s*[Hh小]", ln):
            return _clip(ln)
    for ln in hits:
        if "自理" in ln or "不含" in ln:
            return "雪票自理（" + _clip(ln, 30) + "）"
    return _clip(hits[0])


def extract_photography(text: str) -> str:
    hits = [
        ln for ln in _lines(text)
        if _PHOTO_KW.search(ln) and len(ln) <= MAX_LINE
    ]
    return _clip(hits[0]) if hits else ""


def extract_audience(text: str) -> str:
    m = _AUDIENCE_KW.search(text)
    return m.group(0) if m else ""


# ---------- 入口 ----------

def parse(doc: Doc) -> TripProduct:
    text = doc.text
    days, nights = extract_duration(text)
    return TripProduct(
        code=extract_code(doc),
        title=extract_title(doc),
        days=days,
        nights=nights,
        group_size=extract_group_size(text),
        vehicle=extract_vehicle(text),
        route=extract_route(text),
        stays=extract_stays(text),
        gifts=extract_gifts(text),
        self_pay=extract_self_pay(text),
        skiing=extract_skiing(text),
        photography=extract_photography(text),
        audience=extract_audience(text),
        source_file=doc.name,
        extractor="rules",
    )
