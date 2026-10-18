---
id: F-002
status: done
depends-on: none
blocked-by: none
req: REQ-002
complex-ui: no
schema-approved: yes
api-approved: yes
ux-approved: yes
---

# F-002 — 四态信息状态与原文依据

## 概述

每条对比结论带四态标记（✓/✗/~/?）与原文依据；事实级分类去重；费用语义互斥；独家与差异区分；展示条数与依据条数一致。

## 用户故事

作为选品人，我要能信任报告：每格都能点开看到原文，「没写」不会被当成「不含」，「独家」不会凭空乱标。

## 验收标准

- [x] 四态判定：未提及绝不显示为不包含；肯定与否定并存判「表述模糊」（D-001）
- [x] 一条事实按 CAT_PRIORITY 只在一个展示维度出现，JSON 保留全量（D-002）
- [x] 费用语义互斥：赠送 > 自费 > 明确不含 > 包含；`self_pay` / `excluded` 分离（D-003）
- [x] 「正餐自理」与「骑马自费」文案区分；独家需双向证据
- [x] 「费用包含」跨顿号/逗号/分号/换行不丢条目；展示条数=依据条数（D-004）
- [x] 截断补「…」且括号闭合；赠送转发提示动态计数

## UX 流程

报告矩阵每格：状态 chip + 结论 + 灰色原文依据；新增核心差异摘要区（sumbox）；图例说明四态与独家/差异口径。

## 数据模型影响

| 字段 | 类型 | 约束 | 示例 | 说明 |
|---|---|---|---|---|
| TripProduct.facts | dict[str, Fact] | 11 个维度 | 见 schema.md | 每维度的状态+结论+依据 |
| TripProduct.items | list[ExtractedItem] | 全量 | 见 schema.md | 事实条目（含类别） |
| TripProduct.excluded | list[str] | 新增 | `滑雪：不含` | 明确不包含，从 self_pay 拆出 |

## 输出契约

JSON 新增 `facts`、`items`、`excluded`；`self_pay` 语义收窄（向后兼容：旧字段保留）。报告新增四态 chip、独家/差异标签、摘要区。

## 报告说明

遵循 `report-standards.md`：状态文案按维度细分、MAX_SHOW=4、截断省略号、括号闭合截断。

## 测试计划

- `tests/test_facts.py`：12 项四态判定
- `tests/test_extraction.py`：至 35 项（去重/拆分/误判/独家/依据/截断/字段语义/回归）
- 验收实跑：49/49（2026-10-17）

## 假设

- 关键词锚定覆盖中文跟团游说明书主流写法
- 「费用包含」继承在遇到新段头/日行/新费用语义时终止

## 待定问题

- 真实 PDF 上的噪声表现 → 转入 REQ-003 / F-003

## 关联需求

REQ-002（四态信息状态与原文依据），evolves REQ-001
