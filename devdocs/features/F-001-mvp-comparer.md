---
id: F-001
status: done
depends-on: none
blocked-by: none
req: REQ-001
complex-ui: no
schema-approved: yes
api-approved: yes
ux-approved: yes
---

# F-001 — 行程对比器 MVP

## 概述

从多份旅游产品说明书（PDF/TXT）提取结构化字段，生成一页 HTML 对比矩阵报告，附可选 JSON 结构化输出。

## 用户故事

作为旅行社选品/定制师，我把 N 份线路说明书扔进一个命令，立刻拿到一页能发微信的对比表，不再逐页翻 PDF。

## 验收标准

- [x] 输入文件或目录（PDF/TXT），至少 2 份才可对比
- [x] 提取字段：天数/晚数、团型、用车、行程路线、住宿、赠送、需自理、滑雪、旅拍、定位人群
- [x] 输出单文件 HTML（内嵌样式）+ 可选 `--json` 结构化数据
- [x] 命令：`python -m trip_compare compare <输入…> -o report.html [--json data.json] [--title 标题] [--llm]`

## UX 流程

单页报告：header（标题+生成时间）→ 产品速览卡片 → 对比矩阵 → 图例 → footer。无交互流程。

## 数据模型影响

初版数据模型：TripProduct / Stay（见 `devdocs/schema.md` 变更记录）。五列字段表随后续需求演进，以 schema.md 当前状态为准。

## 输出契约

CLI 子命令 `compare`；JSON 为 `[TripProduct.to_dict(), …]`；HTML 矩阵行 = 固定维度集合。

## 报告说明

初版报告为简单矩阵 + 蓝白配色，无状态标记（四态在 F-002 引入）。

## 测试计划

- `tests/test_parser.py`：字段提取基本断言（2 项）
- 实测：样品两份 + 北疆真实 PDF 四份生成报告，人工核对

## 假设

- 说明书以中文跟团游文案为主，关键词锚定够用
- LLM 引擎为可选增强，默认规则引擎（D-006 前已有此设计）

## 待定问题

- 图片型 PDF 提取率低的兜底方案 → 后转入 I-001（OCR 兜底）

## 关联需求

REQ-001（行程对比器 MVP）
