# trip-compare · 行程对比器

把多份旅游产品说明书（PDF/TXT）扔进去，自动提取结构化字段，生成一页**对比矩阵 HTML 报告**。

> 选品场景的真实痛点：旅行社/定制师同时拿着 N 份线路说明书，靠人肉逐页翻找「几天几晚、住什么、含不含滑雪、送不送旅拍」。trip-compare 把这件事压缩到一条命令。

**[▶ 在线 Demo](https://070605yanghao.github.io/trip-compare/)** —— 合成样品对比报告，浏览器直接打开；另有 [真实四线路对比示例](https://070605yanghao.github.io/trip-compare/beijiang-report.html)。

## 创新点

- **双引擎解析**：规则引擎（零成本、秒出、离线可用）做基线；配置 LLM（任意 OpenAI 兼容接口）后自动升级，结构化精度由模型兜底，LLM 失败自动回退规则结果，永不阻塞。
- **对比而非罗列**：不只提取，还自动计算「独家项」——某维度上只有一家有的配置会高亮，差异一眼可见。
- **区分信息状态**：每条结论都带状态 —— ✓ 明确包含 / ✗ 明确不包含 / ? 原文未提及 / ~ 表述模糊。**「没提取到」不再被当成「不包含」**。
- **结论可回溯**：重要字段附带原文依据，人工一眼可核实，不用再翻原始说明书。
- **零依赖报告**：输出单文件 HTML（内嵌样式），微信里直接发、浏览器直接开，不需要对方装任何东西。

## 快速开始

```bash
pip install -r requirements.txt   # 只有 pypdf 一个依赖

# 对比目录下所有 PDF/TXT
python -m trip_compare compare ./说明书目录 -o output/report.html --json output/data.json

# 对比指定文件
python -m trip_compare compare A.pdf B.pdf C.pdf -o output/report.html
```

试一下自带的样品数据（纯文本，无需 PDF）：

```bash
python -m trip_compare compare samples -o output/sample-report.html
```

## 启用 LLM 引擎（可选）

```bash
# Windows PowerShell
$env:TRIP_LLM_BASE_URL="https://api.openai.com/v1"
$env:TRIP_LLM_API_KEY="sk-..."
$env:TRIP_LLM_MODEL="gpt-4o-mini"

python -m trip_compare compare ./说明书目录 -o output/report.html --llm
```

LLM 抽取结果与规则结果自动合并：LLM 为空/失败的字段回退到规则值。

## 提取字段

| 字段 | 说明 |
|---|---|
| 天数/晚数 | `7天6晚` / `8日` 两种写法都认 |
| 团型 | 如「2-6 人小团」「2 人起订」 |
| 用车 | 头等舱/商务车/指定车型等 |
| 行程路线 | 按 DAY/第N天 顺序拆出的途经点 |
| 住宿 | 每晚地点 + 档位（钻级/木屋/营地） |
| 赠送项目 | 含「赠/赠送」的条目 |
| 需自理 | 餐食、雪票等自理项 |
| 滑雪 / 旅拍 | 是否含票、含几张精修等口径 |
| 定位人群 | 蜜月/亲子/单人等关键词 |

每个字段除取值外，还带 `status`（`included` / `excluded` / `ambiguous` / `unknown`）与 `evidence`（原文依据）：

| 状态 | 含义 | 报告中的处理 |
|---|---|---|
| `included` 明确包含 | 原文有肯定表述（含/包含/赠送…） | ✓ 绿色标记，参与独家项比较 |
| `excluded` 明确不包含 | 原文有否定表述（不含/自理/自费…） | ✗ 红色标记 |
| `ambiguous` 表述模糊 | 只提到关键词、或肯定与否定并存（如「含滑雪体验，雪票自理」） | ~ 橙色标记，需人工确认 |
| `unknown` 未提及 | 原文完全没提 | ? 灰色「未提及」，**不参与独家项比较** |

## 项目结构

```
trip_compare/
├── extract.py       # PDF/TXT 文本提取（含 PDF 代理字符清洗）
├── parser.py        # 规则解析引擎（中文旅游文案关键词锚定）
├── llm_extract.py   # LLM 解析引擎（OpenAI 兼容，纯标准库）
├── compare.py       # 对比矩阵 + 独家项计算
├── report.py        # 单文件 HTML 报告渲染（零依赖）
└── cli.py           # 命令行入口
samples/             # 样品数据（合成，可安全公开）
tests/               # 最小测试
```

## 测试

```bash
python tests/test_parser.py   # 原有：字段提取基本断言
python tests/test_facts.py    # 新增：信息状态判定（含/不含/未提及/模糊/重复）
```

`test_facts.py` 覆盖 12 个用例，重点防回归：明确不包含不能被写成「自理」；未提及必须显示「未提及」；「含 X，X 自理」必须判模糊而不是二选一；自理项不能混进赠送项。

## 已知限制

- 纯图片型 PDF（扫描件）文字层为空，规则引擎提取有限——这正是留给 LLM 引擎的场景；
- 规则引擎针对中文跟团游说明书调优，其他语种/品类需扩展关键词；
- **同一字段在原文多处表述不一致时（如一处写含雪票、一处写雪票自理），统一判为 `ambiguous` 并列出全部证据，不做自动取舍**；
- 赠送/自理条目按子句切分后去重，语义相同但措辞不同的条目（「赠送航拍短片」vs「全团赠送 1 段航拍」）仍可能重复出现；
- 住宿天数、价格等字段尚未纳入状态判定，仍为「提不到即留空」。

## Roadmap

- [ ] OCR 兜底（图片型 PDF）
- [ ] 对比报告导出 PDF/PNG
- [ ] 价格字段与性价比评分
- [ ] Web UI（拖拽上传多份 PDF）

## License

MIT © 杨浩
