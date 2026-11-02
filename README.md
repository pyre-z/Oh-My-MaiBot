# Oh-My-MaiBot

本仓库是 [MaiBot](https://github.com/Mai-with-u/MaiBot) 的个人 fork，仅供本地部署与自用改动使用。

- 上游仓库：<https://github.com/Mai-with-u/MaiBot>
- 上游文档：<https://docs.mai-mai.org>
- 同步基线：MaiBot 1.3.19
- 本 fork 的改动：`git log --oneline origin/main..main`

安装、配置、插件与使用方法请以[上游文档](https://docs.mai-mai.org)为准；Issue 和 PR 请优先提交到上游仓库。

## 本地开发与运行

依赖与虚拟环境统一由 [uv](https://docs.astral.sh/uv/) 管理（`pyproject.toml` + `uv.lock`，不再维护 `requirements.txt`）：

```bash
uv sync          # 按 uv.lock 创建 .venv 并安装依赖
uv run python bot.py  # 在项目虚拟环境中启动
```

改了依赖后执行 `uv lock` 更新 `uv.lock` 再提交。

**License**: GPL-3.0（沿用上游）
