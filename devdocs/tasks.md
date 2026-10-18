# Tasks

> bug / debt / chore。bug、chore 可直接开工；debt 需人批准。
> T 编号永久稳定，关闭移 Closed，删错建条目时编号退役不复用。

## Open

| ID | 类型 | 描述 | 关联功能 | 状态 |
|---|---|---|---|---|
| T-001 | debt | PDF 硬换行会把句子劈成两半（如「不接受游 / 客指定车型的要求」），导致用车等描述型取值出现碎片。缓办理由：修复要动行级合并，会波及「费用包含」跨行继承的现有行为，风险大于收益。重启触发：真实报告可读性被投诉，或要支撑更多版式差异大的说明书 | — | open |

## Closed

| ID | 类型 | 描述 | 处理方式 |
|---|---|---|---|
| T-002 | chore | 本地 git 历史与远端 API 推送历史内容一致但 SHA 分叉（本机 git push 不可用：PortableGit 缺 git-remote-https.exe） | 已统一：用 GitHub Git Data API 按本地 7 个提交的原始 tree / parents / author / committer / message 逐字节复刻，SHA 全部命中（e6a2f31…b2d481b），远端 main 已指向 b2d481b = 本地 HEAD；文件树 39 个文件零差异。后续仍沿用 API 推送，限制已记入 deploy.md |
