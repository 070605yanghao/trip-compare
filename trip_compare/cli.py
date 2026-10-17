# -*- coding: utf-8 -*-
"""命令行入口：

    python -m trip_compare compare <pdf|txt|目录> ... -o report.html [--json data.json] [--llm]
"""
from __future__ import annotations

import argparse
import json
import os
import sys

from . import compare as _compare
from . import extract, parser, report


def _parse_one(path: str, use_llm: bool) -> "object":
    doc = extract.load(path)
    product = parser.parse(doc)
    if use_llm:
        try:
            from . import llm_extract

            product = llm_extract.parse(doc, fallback=product)
        except Exception as e:  # LLM 失败不阻塞，回退规则结果
            print(f"  ! LLM 解析失败，已回退规则引擎：{os.path.basename(path)}（{e}）", file=sys.stderr)
    return product


def cmd_compare(args: argparse.Namespace) -> int:
    paths = extract.gather(args.inputs)
    if len(paths) < 2:
        print("至少需要 2 份说明书才能对比。", file=sys.stderr)
        return 2

    print(f"共 {len(paths)} 份文件：")
    products = []
    for p in paths:
        print(f"  - 解析 {os.path.basename(p)} ...")
        products.append(_parse_one(p, args.llm))

    html = report.render(products, title=args.title)
    os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"\n对比报告 -> {args.output}")

    if args.json:
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump([p.to_dict() for p in products], f, ensure_ascii=False, indent=2)
        print(f"结构化数据 -> {args.json}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        prog="trip-compare",
        description="把多份旅游产品说明书（PDF/TXT）变成一页对比报告",
    )
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("compare", help="对比多份说明书")
    c.add_argument("inputs", nargs="+", help="PDF/TXT 文件或目录")
    c.add_argument("-o", "--output", default="output/report.html", help="HTML 报告输出路径")
    c.add_argument("--json", default=None, help="可选：结构化 JSON 输出路径")
    c.add_argument("--title", default="行程对比报告", help="报告标题")
    c.add_argument("--llm", action="store_true", help="启用 LLM 解析（需配置 TRIP_LLM_* 环境变量）")
    c.set_defaults(func=cmd_compare)
    return ap


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)
