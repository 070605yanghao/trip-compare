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
    self_pay: list[str] = field(default_factory=list)   # 需自理项目
    skiing: str = ""                  # 滑雪口径
    photography: str = ""             # 旅拍/航拍口径
    audience: str = ""                # 定位人群
    source_file: str = ""
    extractor: str = "rules"          # rules | llm
    # 字段判定状态：{维度名: Fact}，维度名与对比矩阵行名一致
    facts: dict[str, Fact] = field(default_factory=dict)

    def fact(self, key: str) -> Fact:
        return self.facts.get(key) or Fact()

    def to_dict(self) -> dict:
        d = asdict(self)
        d["facts"] = {k: v.to_dict() for k, v in self.facts.items()}
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "TripProduct":
        d = dict(d)
        d["stays"] = [Stay(**s) for s in d.get("stays", [])]
        d["facts"] = {k: Fact.from_dict(v) for k, v in (d.get("facts") or {}).items()}
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
