# -*- coding: utf-8 -*-
"""结构化产品模型。"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field


@dataclass
class Stay:
    """一晚住宿。place=地点，level=档位（如 五钻/木屋），note=补充说明。"""

    place: str = ""
    level: str = ""
    note: str = ""


# ---------- 信息状态 ----------
# 四类状态，杜绝「没提取到 == 不包含」的误读。
STATUS_INCLUDED = "included"    # 明确包含
STATUS_EXCLUDED = "excluded"    # 明确不包含
STATUS_AMBIGUOUS = "ambiguous"  # 表述模糊/自相矛盾，无法确认
STATUS_UNKNOWN = "unknown"      # 原文未提及，无法确认（不等于不包含）

STATUS_LABEL = {
    STATUS_INCLUDED: "明确包含",
    STATUS_EXCLUDED: "明确不包含",
    STATUS_AMBIGUOUS: "表述模糊",
    STATUS_UNKNOWN: "未提及",
}
STATUS_MARK = {
    STATUS_INCLUDED: "✓",
    STATUS_EXCLUDED: "✗",
    STATUS_AMBIGUOUS: "~",
    STATUS_UNKNOWN: "?",
}


@dataclass
class Fact:
    """一个字段的判定结果：状态 + 结论 + 原文依据。

    status 见上面四个常量；value 是给人看的结论短语（unknown 时为空）；
    evidence 是命中的原文片段，用于人工核实。
    """

    status: str = STATUS_UNKNOWN
    value: str = ""
    evidence: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {"status": self.status, "value": self.value, "evidence": list(self.evidence)}

    @classmethod
    def from_dict(cls, d: dict) -> "Fact":
        d = d or {}
        return cls(
            status=d.get("status", STATUS_UNKNOWN),
            value=d.get("value", ""),
            evidence=list(d.get("evidence", [])),
        )

    @property
    def label(self) -> str:
        return STATUS_LABEL.get(self.status, self.status)

    @property
    def mark(self) -> str:
        return STATUS_MARK.get(self.status, "?")


# ---------- 事实条目类别 ----------
CAT_SKIING = "skiing"        # 滑雪相关
CAT_PHOTO = "photo"          # 旅拍/航拍相关
CAT_GIFT = "gift"            # 赠送项目
CAT_SELF_PAY = "self_pay"    # 需自理/自费
CAT_EXCLUDED = "excluded"    # 明确不包含
CAT_INCLUDED = "included"    # 包含在费用内（非赠送）

# 展示优先级：一条事实只在一个维度里出现，避免同一条信息重复展示
CAT_PRIORITY = [CAT_SKIING, CAT_PHOTO, CAT_GIFT, CAT_SELF_PAY, CAT_EXCLUDED, CAT_INCLUDED]


@dataclass
class ExtractedItem:
    """一条被切分出来的独立事实（对应原文的一个子句）。

    text      = 事实本身（尽量短，只讲一件事）
    categories= 该事实同时属于哪些类别（如「赠送无人机航拍」= [gift, photo]）
    status    = included / excluded / ambiguous
    evidence  = 支撑它的原文片段
    """

    text: str = ""
    categories: list[str] = field(default_factory=list)
    status: str = STATUS_UNKNOWN
    evidence: str = ""

    def to_dict(self) -> dict:
        return {
            "text": self.text,
            "categories": list(self.categories),
            "status": self.status,
            "evidence": self.evidence,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "ExtractedItem":
        d = d or {}
        return cls(
            text=d.get("text", ""),
            categories=list(d.get("categories", [])),
            status=d.get("status", STATUS_UNKNOWN),
            evidence=d.get("evidence", ""),
        )

    def has(self, cat: str) -> bool:
        return cat in self.categories


@dataclass
class TripProduct:
    """一份旅游产品说明书解析后的结构化结果。"""

    code: str = ""                    # 产品编号（取自文件名，如 J-D11）
    title: str = ""                   # 产品标题
    days: int | None = None
    nights: int | None = None
    group_size: str = ""              # 如 "2-6 人小团"
    vehicle: str = ""                 # 用车说明
    route: list[str] = field(default_factory=list)      # 有序途经点
    stays: list[Stay] = field(default_factory=list)
    gifts: list[str] = field(default_factory=list)      # 赠送项目
    self_pay: list[str] = field(default_factory=list)   # 需自理/自费项目（要另外掏钱）
    excluded: list[str] = field(default_factory=list)   # 明确不包含项目（如「滑雪：不含」）
    skiing: str = ""                  # 滑雪口径
    photography: str = ""             # 旅拍/航拍口径
    audience: str = ""                # 定位人群
    source_file: str = ""
    extractor: str = "rules"          # rules | llm
    # 字段判定状态：{维度名: Fact}，维度名与对比矩阵行名一致
    facts: dict[str, Fact] = field(default_factory=dict)
    # 切分出来的原始事实条目（含类别归属），用于去重与溯源
    items: list[ExtractedItem] = field(default_factory=list)

    def fact(self, key: str) -> Fact:
        return self.facts.get(key) or Fact()

    def items_of(self, dim: str) -> list[ExtractedItem]:
        """属于某个展示维度的事实条目（按 CAT_PRIORITY 归到唯一维度）。"""
        from .compare import DIM_OF_CAT  # 延迟导入，避免循环依赖

        out = []
        for it in self.items:
            for cat in CAT_PRIORITY:
                if it.has(cat):
                    if DIM_OF_CAT.get(cat) == dim:
                        out.append(it)
                    break
        return out

    def to_dict(self) -> dict:
        d = asdict(self)
        d["facts"] = {k: v.to_dict() for k, v in self.facts.items()}
        d["items"] = [i.to_dict() for i in self.items]
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "TripProduct":
        d = dict(d)
        d["stays"] = [Stay(**s) for s in d.get("stays", [])]
        d["facts"] = {k: Fact.from_dict(v) for k, v in (d.get("facts") or {}).items()}
        d["items"] = [ExtractedItem.from_dict(i) for i in (d.get("items") or [])]
        known = {f for f in cls.__dataclass_fields__}
        return cls(**{k: v for k, v in d.items() if k in known})

    def duration(self) -> str:
        if self.days and self.nights:
            return f"{self.days} 天 {self.nights} 晚"
        if self.days:
            return f"{self.days} 天"
        return "—"

    def stay_summary(self) -> str:
        if not self.stays:
            return "—"
        parts: list[str] = []
        for s in self.stays:
            txt = (s.place + " " + s.level).strip()
            if s.note:
                txt += f"（{s.note}）"
            parts.append(txt or "—")
        return "；".join(parts)
