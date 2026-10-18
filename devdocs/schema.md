# 数据模型（schema.md）

> 当前数据模型的唯一事实源。`schema.py` 字段变更时同步更新本文件；JSON 往返测试（test_json_roundtrip_keeps_excluded）是本项目的漂移检查。

## 信息状态（四态）

| 常量 | 值 | 报告标记 | 含义 |
|---|---|---|---|
| STATUS_INCLUDED | `included` | ✓ | 原文有肯定表述 |
| STATUS_EXCLUDED | `excluded` | ✗ | 原文有否定表述（不含/自理/自费…） |
| STATUS_AMBIGUOUS | `ambiguous` | ~ | 表述模糊或自相矛盾，需人工确认 |
| STATUS_UNKNOWN | `unknown` | ? | 原文未提及（不等于不包含，不参与独家判定） |

## 事实条目类别（CAT）

| 常量 | 值 | 展示维度 |
|---|---|---|
| CAT_SKIING | `skiing` | 滑雪 |
| CAT_PHOTO | `photo` | 旅拍 |
| CAT_GIFT | `gift` | 赠送项目 |
| CAT_SELF_PAY | `self_pay` | 需自理 |
| CAT_EXCLUDED | `excluded` | 需自理（与自费合并展示） |
| CAT_INCLUDED | `included` | 包含服务 |

展示优先级 `CAT_PRIORITY = [skiing, photo, gift, self_pay, excluded, included]`：一条事实按此顺序归到唯一展示维度（D-002）。

## TripProduct

| 字段 | 类型 | 约束 | 示例 | 说明 |
|---|---|---|---|---|
| code | str | 可空 | `J-D11` | 产品编号，从文件名头部提取 |
| title | str | 可空 | `双湖之恋 7 日.1+1 头等舱` | 产品标题；正文无标题行时回退文件名 |
| days / nights | int\|None | 可空 | `7` / `6` | 正文提不到时回退文件名（依据注明来源） |
| group_size | str | 可空 | `2-6 人小团` | |
| vehicle | str | 可空 | `专属 1+1 头等舱车型` | |
| route | list[str] | ≤14 项 | `["出发地","乌鲁木齐",…]` | 有序途经点，丢弃括号未闭合的碎片 |
| stays | list[Stay] | ≤12 项 | 见下 | |
| gifts | list[str] | | `["赠送无人机航拍一段"]` | 赠送条目全量（含归到旅拍/滑雪的） |
| self_pay | list[str] | | `["正餐自理"]` | 需自理/自费（要另外掏钱） |
| excluded | list[str] | | `["滑雪：不含"]` | 明确不包含（D-003 从 self_pay 拆出） |
| skiing / photography / audience | str | 可空 | | 口径摘要；unknown 时为空，状态看 facts |
| source_file | str | | `J-D11.双湖之恋7日1+1头等舱` | |
| extractor | str | | `rules` | `rules` 或 `llm` |
| facts | dict[str, Fact] | | | 11 个维度的判定结果 |
| items | list[ExtractedItem] | | | 全部事实条目（JSON 保留全量） |

## Fact

| 字段 | 类型 | 说明 |
|---|---|---|
| status | str | 四态之一 |
| value | str | 结论短语；unknown 时为空；列表维度最多展示 MAX_SHOW=4 条 + 「（共 N 条）」 |
| evidence | list[str] | 原文依据，条数不少于展示条数（D-004） |

## ExtractedItem

| 字段 | 类型 | 说明 |
|---|---|---|
| text | str | 事实本身（≤50 字，不含公共段头前缀） |
| categories | list[str] | 可同时属多类（如「赠送无人机航拍」= [gift, photo]） |
| status | str | 四态之一 |
| evidence | str | 完整原文片段（≤60 字，保留段头便于核实） |

## Stay

| 字段 | 类型 | 说明 |
|---|---|---|
| place | str | 地点 |
| level | str | 档位（五钻/木屋/营地…） |
| note | str | 补充说明（来自「参考酒店：」行） |

## 维度名（facts 的 key）

行程天数 / 住宿配置 / 行程覆盖 / 团型 / 用车 / 滑雪 / 旅拍 / 赠送项目 / 包含服务 / 需自理 / 定位人群

## 变更记录

- 2026-10-17：新增 `excluded` 字段（D-003）；`self_pay` 语义收窄为只含自理/自费。
- 2026-10-18：标题与天数增加文件名兜底策略（D-005），字段结构未变。
