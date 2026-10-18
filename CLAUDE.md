# CLAUDE.md

> 本文件是 trip-compare 的开发流程宪法，改编自老师分享的 claude-dev-system。
> 每个写代码的会话（Claude Code / WorkBuddy / Codex 等）开始前都必须先读它。

## 这是什么

trip-compare 是一个**行程对比器**：把多份旅游产品说明书（PDF/TXT）扔进去，自动提取结构化字段（天数、住宿、滑雪、旅拍、赠送、自理…），生成一页带四态标记（✓包含 / ✗不包含 / ~模糊 / ?未提及）和原文依据的 HTML 对比矩阵。纯 Python，唯一依赖 pypdf，报告零依赖单文件。线上 Demo 由 `docs/` 目录经 GitHub Pages 发布。

## 项目如何运转

- **需求由人定义**：写在 `devdocs/product-requirements.md`（REQ-001、REQ-002…）。AI 不主动改需求文本；人要求改时，改动与理由记入 `decisions.md`。
- **功能拆解由 AI 提议、人批准**后才开工。工作顺序按 F 编号，人可在 `backlog.md` 的 `## Up Next` 置顶插队。
- **AI 驱动**实现、backlog 维护和文档；**人审批**功能拆解、顺序、数据模型、输出契约、报告样式，以及所有 `review → done`。
- **拆解必须完整**：一个需求被拉进来拆解时，它的所有功能都要进 backlog，不允许拆一半。
- **低风险歧义**：AI 在功能文件的 `## Assumptions` 里记录假设后继续。**高风险歧义**（见「提问政策」）必须停下来先问。

---

## 文件地图

| 文件 | 用途 | 谁负责 |
|---|---|---|
| `CLAUDE.md` | 本文件，每个会话的入口 | AI 只能改 `## 当前焦点` |
| `devdocs/product-requirements.md` | 需求主列表（REQ-XXX） | 人写 |
| `devdocs/requirements-index.md` | 需求状态与演化链 | AI 维护；evolves 链接需人批准 |
| `devdocs/backlog.md` | 功能队列 + blocked/deferred | AI 维护；顺序与置顶由人定 |
| `devdocs/tasks.md` | bug / 技术债 / 杂务 | AI 维护；debt 开工前需人批准 |
| `devdocs/ideas.md` | 产品点子收件箱 | AI 起草；增删都要人批准 |
| `devdocs/req-drafts.md` | AI 起草的候选需求 | AI 起草；人决定录用或否决 |
| `devdocs/decisions.md` | 只追加的决策日志 | AI 追加，从不改写 |
| `devdocs/tech-stack.md` | 技术栈定义与理由 | 人批准变更 |
| `devdocs/deploy.md` | 构建/部署/运维手册 | AI 维护（见栈变更对齐规则） |
| `devdocs/schema.md` | 当前数据模型（TripProduct / Fact / JSON 字段） | AI 在数据模型变更时同步更新 |
| `devdocs/extraction-standards.md` | 解析与分类规范（关键词锚定、费用语义互斥、状态判定、证据规则） | 人批准变更；AI 改 parser.py 前必读 |
| `devdocs/report-standards.md` | 报告渲染规范（四态标记、独家/差异、截断、配色） | 人批准变更；AI 改 report.py 前必读 |
| `devdocs/features/F-XXX-name.md` | 每个功能的完整规格 | AI 创建与维护 |

注意：`docs/` 是 GitHub Pages 的发布目录（线上 Demo），**不是**流程文档的家。流程文档一律放 `devdocs/`。

---

## 本地开发命令

- **全部测试：** `python tests/test_parser.py && python tests/test_facts.py && python tests/test_extraction.py`（无 pytest，用各文件自带的 `__main__` 运行器；任何提交前必须全绿）
- **生成样品报告：** `python -m trip_compare compare samples -o output/sample-report.html --json output/sample-data.json`
- **生成真实报告：** `python -m trip_compare compare <pdf目录> -o output/beijiang-report.html --json output/beijiang-data.json --title 北疆冬游四线路对比报告`
- **文档漂移检查：** `python scripts/check-docs-drift.py` — 任何改动 `devdocs/` 的提交前必须 exit 0，有漂移先对齐。纯标准库。
- **渲染检查：** Chrome 无头截图 `chrome --headless=new --screenshot=out.png --window-size=1400,2600 file:///…/output/sample-report.html`，改 report.py 后必做。
- `output/` 已 gitignore；`docs/` 里的报告是 `output/` 生成物的拷贝。

---

## 上下文管理

AI 只读与 `## 当前焦点` 直接相关的文件和正在处理的 F-XXX 文件。不要主动通读整个 `devdocs/`，除非明确要求交叉核对或依赖需要。

---

## 命名约定

- **需求**：`REQ-001`、`REQ-002`，在 `product-requirements.md` 中排序，序号 = 优先级。
- **功能**：`docs/features/` 下放 `devdocs/features/F-001-kebab-case.md`，按预期构建顺序编号，人批准。
- **任务**：`T-001`、`T-002`，在 `devdocs/tasks.md` 中，不单独立文件。T 编号永久稳定，绝不重排；关闭即从 Open 移到 Closed（编号不变），删错建的条目时编号退役不复用。
- **点子**：`I-001` 起连续编号，删除一条后后面的全部前移（位置编号，不是稳定引用）。
- **ID 引用**：会话输出中首次引用任何带编号的条目（REQ/F/T/I/D）时，附一句话说明，如 "T-001（PDF 硬换行碎片）"。之后可用裸编号。

---

## 状态定义

**需求（REQ）**：`ready`（待拆解）/ `in-progress`（至少一个功能在建）/ `done`（所属功能全部 done）/ `deferred`（有意推迟，必须写重启触发条件）。

**功能（F）**：

| 状态 | 含义 |
|---|---|
| `backlog` | 已识别，未写规格 |
| `drafted` | AI 已写完整规格，等人批 |
| `ready` | 人批准规格，AI 可以写代码 |
| `in-progress` | 代码在写 |
| `review` | 代码完成、测试通过，等人验收 |
| `done` | 人已验收 |
| `blocked` | 无法推进，原因已记录 |
| `deferred` | 有意推迟，必须写重启触发条件 |

关键规则：AI 写完规格置 `drafted`；人批准后才进 `ready`。AI 可以把功能置 `blocked`/`deferred`，但**没有人批准不能移出**。

**任务（T）**：`open` / `in-progress` / `done`。

---

## 功能生命周期

```
backlog → [AI 写完整规格] → drafted
       → [人审数据模型]   → schema-approved: yes
       → [人审输出契约]   → api-approved: yes
       → [人审报告样式]   → ux-approved: yes
       → ready → [AI 实现：解析引擎 → 对比逻辑 → 报告渲染]
       → in-progress → [测试全绿] → review
       → [人验收] → done
```

**三道闸门的本项目映射：**

| 闸门 | 含义 | 典型内容 |
|---|---|---|
| schema-approved | 数据模型 | `schema.py` 的 dataclass 字段、JSON 输出结构、`schema.md` 同步 |
| api-approved | 输出契约 | CLI 参数、JSON 字段语义（gifts/self_pay/excluded…）、报告 HTML 的维度集合 |
| ux-approved | 报告样式 | 标记文案、配色、截断规则、摘要区结构 |

**实现顺序**：解析引擎（parser.py）→ 对比逻辑（compare.py）→ 报告渲染（report.py）。永远不倒着来：展示层不许先于数据层定稿。

**数据模型漂移**：trip-compare 没有数据库，对应物是 JSON 结构——`tests/test_extraction.py` 的 `test_json_roundtrip_keeps_excluded` 等往返测试就是漂移检查。改了 `schema.py` 字段必须同步 `devdocs/schema.md`，并让往返测试继续通过。发现漂移时 AI 停下来，把脚本/测试输出、诊断、建议方案摆给人，不擅自对齐。

---

## 规格批准后改规格

人要求修改已到 `ready` 或更后的功能文件/需求时，AI 必须先重读整个文件，找出所有受影响的章节（尤其 `## 验收标准` 和 `## 测试计划`），把完整修改方案摆给人批准后再动手。

---

## 功能 metadata 块

每个功能文件开头必须是：

```
---
id: F-XXX
status: backlog
depends-on: F-XXX, F-XXX | none
blocked-by: none | [描述]
req: REQ-XXX[, REQ-XXX]
complex-ui: yes | no
schema-approved: no
api-approved: no
ux-approved: no
---
```

- 置 `drafted` 前检查 `depends-on`：依赖未 `done` 则留在 `backlog`。
- `complex-ui: yes` 表示报告结构/交互有明显复杂度，从 `drafted` 进 `ready` 前人要先看效果（截图或本地 HTML）。
- **三个 approved 标志只有人能改成 yes，AI 不许碰。**

---

## 需求演化链

需求会演化：REQ-003 可能改变 REQ-001 建立的行为。`requirements-index.md` 是已拆解需求状态与关系的唯一事实源：

```
| REQ | 状态 | Evolves | Evolved By | Features |
```

- 索引行在**拆解时**创建，不在写 PRD 时创建。PRD 里有、索引里没有 = 等待拆解。
- 拆解时若该需求是从 `ideas.md` 毕业的，顺手删掉对应点子并重排编号。
- **AI 提议 evolves 链接，人批准**；批准后双向都写（新需求写 Evolves，旧需求写 Evolved By）。
- 给带演化链的需求写规格前，必须沿链（前后双向）读完所有相关需求与功能文件——这是强制的。
- 新需求与旧需求冲突时，新的赢，但必须在功能文件 `## Assumptions` 里写明覆盖了谁、改了什么。
- 被问"某功能现在怎么工作"时，沿演化链读完后综合回答。
- `product-requirements.md` 只放需求正文，状态/链接/演化元数据全在索引里。

---

## 功能粒度规则

一个功能 = 一个连贯的用户可感知能力：1-3 天可完成、有单一可测试的 done 状态。太长就拆；是子任务就写进功能文件里，不单独立项；任务长大到需要规格 → 升级为功能（走最小 REQ + evolves 链接，不许挂到已 done 的旧 REQ 名下）。

---

## 文档归属规则

文档是为未来的可发现性服务的。归属判断：

- **PRD（REQ）**：用户可感知的产品行为，人写。
- **功能（F-XXX）**：永远是某个 REQ 的拆解，不允许无 REQ 立功能。
- **任务（T-XXX）**：其余一切。问一句"本次会话提交后它还是个未解决的问题吗？"——不是就别建任务。
  - 该进 tasks.md 的：已上线的真实 bug；明知存在但决定缓办的技术债（要写清取舍和重启触发条件）；与进行中功能无关的杂务。
  - 不该进的：开发/UAT 中发现并已修掉的问题（git 历史就是记录）；review 中发现的测试缺口（同一周期内补掉）；AI 顺手完成的小重构。
- 流程/系统决策记在 CLAUDE.md 可达的文档里，不记在会话记忆里。拿不准放哪就问人。

---

## 功能文件结构

每个 `devdocs/features/F-XXX-name.md` 必须含：

```
## 概述
## 用户故事
## 验收标准
## UX 流程          ← 进 ready 前需人批准（本项目 = 报告呈现/交互）
## 数据模型影响     ← 进 ready 前需人批准
## 输出契约         ← 进 ready 前需人批准（CLI/JSON/HTML 维度变化）
## 报告说明
## 测试计划
## 假设
## 待定问题
## 关联需求
```

- `## 数据模型影响`：新增/变更的字段用五列表格写清：名称、类型、约束、示例值、说明。含糊字段（状态、类别）必须给具体示例值。改 parser 分类规则前必读 `extraction-standards.md`。
- `## 输出契约`：CLI 参数变化、JSON 字段的新增/语义、报告新增的维度行。人批准后 AI 才能动。
- `## 报告说明`：改 report.py 前必读 `report-standards.md`；四态标记的文案、独家/差异标签的判定口径、截断与省略号规则都不能私自偏离。

---

## backlog 结构

```
## Up Next
[人置顶的 F 编号，按列出顺序做，做完自动移除]

## Priority Queue
| ID | 功能 | 状态 | 依赖 | 需求 |

## Blocked
| ID | 功能 | 阻塞原因 | 起始日期 |

## Deferred
| ID | 功能 | 原因 | 重启触发条件 |
```

done 的功能保留在 Priority Queue 里（状态 done），不删除——漂移脚本要求文件与表格双向覆盖。

---

## tasks 结构

```
## Open
| ID | 类型 | 描述 | 关联功能 | 状态 |

## Closed
| ID | 类型 | 描述 | 处理方式 |
```

类型：`bug` / `debt` / `chore`。bug 和 chore AI 可直接开工；debt 开工前需人批准（可能有架构影响）。

---

## 点子收件箱

`ideas.md` 放低承诺的未来需求，保持低数量。触发：人说"记一下/加到点子/以后再说"；或 AI 在实现中发现产品级缺口并提议。流程：AI 起草 `I-NNN — 标题` + 1-3 句描述 → 人批准 → 写入。升级为 REQ 由人亲手写进 PRD，点子本身在**拆解时**由 AI 删除并重排。

---

## bug 升级政策

对任何 bug（不论从哪冒出）：AI 跟踪每个问题的修复次数。**第二次尝试**前必须停下来，用大白话讲诊断和方案，等人确认；信息不够就明确请人做具体操作并回报结果，不许猜。**第三次起**还要先总结之前试过什么、为什么没成。

---

## 子代理规则

派生任何写代码的子代理，prompt 必须包含：

"读 CLAUDE.md（尤其文件地图一节），并读与你的任务相关的规范文件，遵守其中全部规则。"

并且直接在 prompt 里点名具体文件：改 parser → `devdocs/extraction-standards.md`；改报告 → `devdocs/report-standards.md`；改数据模型 → 加 `devdocs/schema.md`。子代理是白板，不点名就不会读——这是规范失效的最大来源。

---

## "下一步做什么" 协议

人说"做下一个"时：
1. 先看 `backlog.md` 的 `## Up Next`，按列出顺序做；
2. 空的 → 找编号最小的 `ready` 功能；
3. 没有 `ready` → 把所有 `drafted`/`blocked`/`deferred` 摆给人，不许静默跳过；
4. 全部 `done` 且 Up Next 空 → 扫 PRD 里无索引行的需求（等待拆解），多于一个时提议最小可测的纵向切片，人批准拉哪些。一次只往 `ready` 里放一个切片的量。

---

## 验收协议

功能进 `review` 时，AI 必须主动给出总结，包含：
1. **做了什么**（大白话）
2. **与规格的偏差**及原因
3. **做过的假设**
4. **自动化测试结果**：执行的命令 + 通过/失败数（不许引用历史结果，当次实跑）
5. **数据模型对齐**（有 schema 变化时）：`schema.md` 已同步、往返测试通过
6. **UAT 建议**：人在本地怎么验证的具体步骤（如重新生成报告、检查某行标记）；人要 UAT 清单时写到项目根目录 `uat-checklist.md`（已 gitignore，checkbox 格式），验收完成后删除

人等"看起来没问题""测过了"这类信号时，AI 要主动确认是否置 `done` 并更新 backlog/索引/当前焦点——不许干等"approve"这个词。review 周期内发现的问题在同一周期内修，不回退到 `in-progress`，也不建 tasks 条目。

---

## 测试政策

测试不是可选项，随功能一起写。

**覆盖清单（本项目实际）：**
- `tests/test_parser.py`：字段提取基本断言
- `tests/test_facts.py`：四态判定（含/不含/未提及/模糊/重复）
- `tests/test_extraction.py`：提取与分类（去重/拆分/误判/独家/依据/截断/字段语义/真实 PDF 加固/回归）

**规则：**
- 进 `review` 前全绿，结果写进功能文件 `## 测试计划`（当次实跑）
- **测试计划审计**：进 `review` 前把 `## 测试计划` 逐行对照实际测试文件，列了没测的必须报出来
- **回归红线**：误判类用例（未提及→不包含、自理→自费、赠送重复展示等）一旦写过测试就不许删改语义，只能加新用例
- 改了报告渲染 → 必须附 Chrome 无头截图核对实际显示

---

## 部署协议

人问"怎么发布/上线/更新 Demo"时，不许只回答提到的那个组件：
1. **先盘点全部变更**：代码（trip_compare/）、测试、README、`docs/` 演示页（index.html / beijiang-report.html / JSON）。
2. **给出正确顺序的完整步骤**：测试全绿 → 重新生成 `output/` 报告 → 拷贝进 `docs/` → 本地提交 → 推送远端。
3. **每步给出验证方式**：如推送后查 Pages build 状态、访问线上页面确认新标记出现。
完整命令与凭据细节在 `devdocs/deploy.md`。

---

## 提问政策

以下歧义 AI 必须先问再动：数据模型或 JSON 结构；输出契约（CLI/报告维度）；推送到远端、发布等对外动作；任何不可逆的设计选择。其余歧义记录假设后继续。

---

## 安全红线

- 绝不把密钥、token、凭据提交进仓库；一律走环境变量或本机凭据管理器
- 怀疑密钥泄露：立即停止功能工作，在 `decisions.md` 记录泄露点与补救步骤，并告知人
- 写完用于推送的临时脚本（含读凭据逻辑）后必须删除，不留在工作区

---

## 依赖政策

加任何新库需人批准，AI 要先提出：解决什么问题、考虑过哪些方案、各自取舍、最小可行选择。批准前不安装。

---

## 栈变更对齐规则

任何增删换系统组件的改动（新依赖、新环境变量、新脚本、新发布渠道），必须在同一改动里更新 `devdocs/tech-stack.md`；影响构建/部署/运维的，还要更新 `devdocs/deploy.md`。两个文件必须始终反映现实。进 `review` 前自查：这次改动有没有增删换组件？有的话两个文件更新了吗？

---

## CLAUDE.md 保护规则

AI 只能改本文件的 `## 当前焦点` 一节，其余全部冻结。认为某条规则需要改时：在会话输出里明确提出建议措辞 → 等人批准 → 才可编辑。流程类变更不记进 `decisions.md`（那是产品与架构决策的地方）。

---

## 会话协议

**开始**：读本文件 → 看 `## 当前焦点` → 只加载相关功能文件。
**结束**：更新 backlog 状态 → 追加 decisions → 更新 `## 当前焦点` → 功能进 `ready` 时把链接补进索引行 → 按功能状态滚动需求状态 → 有 schema 变化时同步 `schema.md` 并跑往返测试 → 本次会话改过/建过 `devdocs/` 任何文件，逐条向人汇报改了什么、为什么。

---

## 当前焦点

系统已于 2026-10-18 回填完毕：REQ-001~003 全部 done（对应 F-001~F-003），56 项测试全绿，线上 Demo 已同步。下一个候选方向见 `devdocs/ideas.md`（I-001 OCR 兜底 / I-002 导出 PDF/PNG / I-003 价格字段 / I-004 Web UI），等人选一个写成 REQ。
