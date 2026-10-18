# 技术栈

> 栈的「是什么」与「为什么」的唯一事实源，必须始终反映现实（见 CLAUDE.md 栈变更对齐规则）。

## Stack Overview

| 层 | 选择 | 说明 |
|---|---|---|
| 语言 | Python 3.13 | 无框架，纯脚本项目 |
| 依赖 | pypdf | 唯一第三方依赖，PDF 文字层提取 |
| 报告 | 手写 HTML 模板（report.py 字符串拼接） | 零依赖单文件输出，微信/浏览器直接开 |
| 测试 | 各测试文件自带 `__main__` 运行器 | 环境无 pytest；`python tests/xxx.py` 直接跑 |
| 版本控制 | git（PortableGit，本机缺 git-remote-https.exe） | 推送走 GitHub REST API（见 deploy.md） |
| 发布 | GitHub Pages，源为 main 分支 `docs/` 目录 | 演示页 = output/ 生成物的拷贝 |
| 渲染核查 | Chrome 无头截图 | `--headless=new --screenshot`，改报告后必做 |

## Rationale

- **纯标准库 + pypdf**：选品场景的使用者不是开发者，依赖越少越容易跑起来；报告手写 HTML 而不是模板引擎，是为了输出物零依赖。
- **不用 pytest**：本机环境没有也不强制装，自带运行器保证任何机器上 `python tests/xxx.py` 就能验。
- **双引擎预留**：`llm_extract.py` 支持任意 OpenAI 兼容接口（TRIP_LLM_* 环境变量），规则引擎做基线，LLM 失败自动回退——目前默认关闭。

## Dependencies

| 包 | 为什么 |
|---|---|
| pypdf | PDF 文字层提取；纯文本输入时不需要 |

## Environment Variables

| 变量 | 用途 |
|---|---|
| TRIP_LLM_BASE_URL | LLM 引擎接口地址（可选） |
| TRIP_LLM_API_KEY | LLM 引擎密钥（可选，绝不入库） |
| TRIP_LLM_MODEL | LLM 模型名（可选） |
