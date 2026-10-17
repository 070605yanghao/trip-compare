# -*- coding: utf-8 -*-
"""可选的 LLM 解析引擎（OpenAI 兼容接口，纯标准库实现）。

用法：
    export TRIP_LLM_BASE_URL=https://api.openai.com/v1
    export TRIP_LLM_API_KEY=sk-...
    export TRIP_LLM_MODEL=gpt-4o-mini

LLM 输出为 JSON，与 TripProduct 字段一一对应；缺字段由规则解析结果兜底。
"""
from __future__ import annotations

import json
import os
import urllib.request

from .extract import Doc
from .schema import TripProduct

_PROMPT = """你是旅游产品信息抽取器。从下面的旅游产品说明书中抽取结构化字段，输出严格 JSON：
{
  "code": "产品编号，没有则空字符串",
  "title": "产品标题",
  "days": 天数(int|null), "nights": 晚数(int|null),
  "group_size": "如 2-6 人小团，没有则空字符串",
  "vehicle": "用车说明一句话",
  "route": ["按行程顺序的途经点"],
  "stays": [{"place": "地点", "level": "档位", "note": "补充"}],
  "gifts": ["赠送项目短语"],
  "self_pay": ["需自理项目短语"],
  "skiing": "滑雪相关口径一句话",
  "photography": "旅拍/航拍口径一句话",
  "audience": "目标人群一个词"
}
只输出 JSON，不要任何解释。

说明书全文：
"""


def _chat(base: str, key: str, model: str, prompt: str, text: str) -> dict:
    url = base.rstrip("/") + "/chat/completions"
    body = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": prompt + text[:24000]}],
        "temperature": 0,
        "response_format": {"type": "json_object"},
    }).encode("utf-8")
    req = urllib.request.Request(
        url, data=body, method="POST",
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {key}"},
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    content = data["choices"][0]["message"]["content"]
    return json.loads(content)


def available() -> bool:
    return bool(os.environ.get("TRIP_LLM_API_KEY") and os.environ.get("TRIP_LLM_MODEL"))


def parse(doc: Doc, fallback: TripProduct | None = None) -> TripProduct:
    """LLM 解析；失败或缺字段时回退到规则解析结果。"""
    base = os.environ.get("TRIP_LLM_BASE_URL", "https://api.openai.com/v1")
    key = os.environ["TRIP_LLM_API_KEY"]
    model = os.environ["TRIP_LLM_MODEL"]
    data = _chat(base, key, model, _PROMPT, doc.text)

    if fallback is None:
        fallback = TripProduct(source_file=doc.name)
    merged = TripProduct.from_dict(fallback.to_dict())
    fields = set(TripProduct.__dataclass_fields__) - {"stays", "extractor", "source_file"}
    for k, v in data.items():
        if k in fields and v not in (None, "", [], {}):
            setattr(merged, k, v)
    if data.get("stays"):
        from .schema import Stay
        merged.stays = [Stay(**s) for s in data["stays"] if isinstance(s, dict)]
    merged.extractor = "llm"
    merged.source_file = doc.name
    return merged
