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

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "TripProduct":
        d = dict(d)
        d["stays"] = [Stay(**s) for s in d.get("stays", [])]
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
