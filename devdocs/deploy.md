# 部署 / 发布手册

> 「怎么构建、怎么发布、怎么运维」的唯一事实源。

## 本地开发

```bash
pip install -r requirements.txt    # 只有 pypdf
python tests/test_parser.py && python tests/test_facts.py && python tests/test_extraction.py
python -m trip_compare compare samples -o output/sample-report.html --json output/sample-data.json
```

## 线上 Demo 发布流程（docs/ → GitHub Pages）

Demo 页是 `output/` 生成物的拷贝，**不要手改 `docs/` 里的 HTML**：

```bash
# 1. 重新生成
python -m trip_compare compare samples -o output/sample-report.html --json output/sample-data.json --title 行程对比报告
python -m trip_compare compare <真实PDF目录> -o output/beijiang-report.html --json output/beijiang-data.json --title 北疆冬游四线路对比报告

# 2. 拷贝进 docs/
cp output/sample-report.html docs/index.html
cp output/sample-data.json   docs/sample-data.json
cp output/beijiang-report.html docs/beijiang-report.html
cp output/beijiang-data.json   docs/beijiang-data.json
```

3. 本地提交（`git add -A && git commit`）。
4. 推送：本机 `git push` 不可用（PortableGit 缺 `git-remote-https.exe`），走 GitHub REST API：`PUT /repos/070605yanghao/trip-compare/contents/<path>`，token 从 Windows 凭据管理器 `GitHub - https://api.github.com/070605yanghao` 读取。**推送脚本用完即删**（见 CLAUDE.md 安全红线）。
5. 验证：`GET /repos/.../pages/builds/latest` 看 `status=built`；访问 https://070605yanghao.github.io/trip-compare/ 确认新内容出现。

## 已知坑

- 本机 `git push` 不可用，只能走 API。两种 API 推送方式，按场景选：
  - **日常增量**：`PUT /contents/<path>` 逐文件写（base64 + 上次 sha），简单但每个文件一个提交，历史会变长。
  - **对齐历史**：`POST /git/blobs` → `POST /git/trees` → `POST /git/commits` → `PATCH /git/refs/heads/main`（force）。只要 tree / parents / author / committer / message 与本地一致，SHA 就会逐字节命中，远端历史可与本地完全统一（T-002 就是这么解决的）。
  - 日期必须写成 `+08:00`，写成 `+0800` 会被 422 拒。
- Pages 构建需要 1-3 分钟，push 后立刻看是旧版属正常。
- PowerShell 重定向 git 输出会把 UTF-8 中文读成 GBK 乱码——验证提交信息用 Python subprocess 按 utf-8 解码。

## 回滚

Pages 直接重新发布旧版文件即可（`PUT contents` 用旧内容）；代码回滚用 git revert。
