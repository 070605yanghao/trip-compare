# Tasks

> bug / debt / chore。bug、chore 可直接开工；debt 需人批准。
> T 编号永久稳定，关闭移 Closed，删错建条目时编号退役不复用。

## Open

| ID | 类型 | 描述 | 关联功能 | 状态 |
|---|---|---|---|---|
| T-001 | debt | PDF 硬换行会把句子劈成两半（如「不接受游 / 客指定车型的要求」），导致用车等描述型取值出现碎片。缓办理由：修复要动行级合并，会波及「费用包含」跨行继承的现有行为，风险大于收益。重启触发：真实报告可读性被投诉，或要支撑更多版式差异大的说明书 | — | open |
| T-002 | chore | 本地 git 历史（552c49e）与远端 API 推送历史（a3942bf 等）内容一致但 SHA 分叉；本机 git push 不可用（PortableGit 缺 git-remote-https.exe）。待办：统一历史（rebase 或重装完整 git），或长期接受 API 推送方式并在 deploy.md 固化 | — | open |

## Closed

| ID | 类型 | 描述 | 处理方式 |
|---|---|---|---|
