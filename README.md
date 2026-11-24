<a id="-双语--bilingual"></a>

<div align="center">

  <!-- Language Switcher -->
  <p>
    <a href="#-双语--bilingual"><picture><source media="(prefers-color-scheme: dark)" srcset="depends-data/readme/key-lang-bilingual-night.svg"><img src="depends-data/readme/key-lang-bilingual-day.svg" alt="双语 / Bilingual"></picture></a>
    <a href="docs/README_CN.md"><picture><source media="(prefers-color-scheme: dark)" srcset="depends-data/readme/key-lang-zh-night.svg"><img src="depends-data/readme/key-lang-zh-day.svg" alt="中文"></picture></a>
    <a href="docs/README_EN.md"><picture><source media="(prefers-color-scheme: dark)" srcset="depends-data/readme/key-lang-en-night.svg"><img src="depends-data/readme/key-lang-en-day.svg" alt="English"></picture></a>
  </p>

  <!-- Hero -->
  <picture><source media="(prefers-color-scheme: dark)" srcset="depends-data/readme/hero-night.svg"><img src="depends-data/readme/hero-day.svg" alt="麦麦 MaiBot：致力于了解你，用真人的方式聊天的数字生命" width="100%"></picture>

  <p><strong>Oh-My-MaiBot</strong> &middot; 基于上游 MaiBot v1.4.8 &middot; WebUI 1.10.8</p>

  <!-- Badges Row -->
  <p>
    <img src="https://img.shields.io/badge/Python-3.13-8fd6a0?style=flat-square&labelColor=5a544a" alt="Python Version">
    <img src="https://img.shields.io/github/license/pyre-z/Oh-My-MaiBot?label=License&color=8fd6a0&style=flat-square&labelColor=5a544a" alt="License">
    <img src="https://img.shields.io/badge/upstream-MaiBot%20v1.4.8-f08a5d?style=flat-square&labelColor=5a544a" alt="Upstream">
    <img src="https://img.shields.io/badge/base-GPL--3.0%20fork-ffd84a?style=flat-square&labelColor=5a544a" alt="Fork">
  </p>

  <!-- Quick links -->
  <p>
    <a href="https://github.com/Mai-with-u/MaiBot"><picture><source media="(prefers-color-scheme: dark)" srcset="depends-data/readme/key-docs-night.svg"><img src="depends-data/readme/key-docs-day.svg" alt="上游仓库"></picture></a>
    <a href="https://docs.maibot.chat"><picture><source media="(prefers-color-scheme: dark)" srcset="depends-data/readme/key-website-night.svg"><img src="depends-data/readme/key-website-day.svg" alt="上游文档"></picture></a>
    <a href="#-相比上游的改动"><picture><source media="(prefers-color-scheme: dark)" srcset="depends-data/readme/key-setup-night.svg"><img src="depends-data/readme/key-setup-day.svg" alt="改动清单"></picture></a>
  </p>
</div>

---

## 📌 这是什么

本仓库是 [Mai-with-u/MaiBot](https://github.com/Mai-with-u/MaiBot) 的**个人私有 fork**，供自建部署与本地改造使用，**不是**官方发行版。

- **上游仓库**：<https://github.com/Mai-with-u/MaiBot>
- **上游文档**：<https://docs.maibot.chat>（安装、配置、插件、使用均以上游文档为准）
- **同步基线**：MaiBot **v1.4.8** / WebUI **1.10.8**
- **本 fork 改动**：见下方[相比上游的改动](#-相比上游的改动)，完整清单以 `git log --oneline upstream/main..main` 为准

> Issue 与 PR 请优先提交上游；本仓库只维护自己需要的改动。

## 🚀 部署方式

本 fork 以**源码构建镜像**方式部署，不使用上游官方镜像。

```bash
git clone https://github.com/pyre-z/Oh-My-MaiBot.git
cd Oh-My-MaiBot
docker compose build core      # 构建 oh-my-maibot:<上游版本>-fork.N
docker compose create core && docker start core
```

- 镜像标签格式 `<上游版本>-fork.N`（当前 `oh-my-maibot:1.4.8-fork.0`），避免与上游同号误判。
- WebUI 默认只绑 `127.0.0.1:18001`，对外请自行反代。
- **前端源码改动后需单独重建**：`docker-compose.override.yml` 把宿主机 `dashboard/dist` 挂进容器，
  `docker compose build core` 不会重编前端。改 `dashboard/` 后要执行：

```bash
cd dashboard && pnpm install && pnpm build   # dist 已被 .gitignore 排除，只在本地生成
```

## 🔧 相比上游的改动

### 1. 本地部署适配

- `Dockerfile` 内置 `ffmpeg` / `ffprobe`，动图抽帧等能力开箱可用。
- `docker-compose.yml` 改为本地 `build` 镜像、端口只绑 `127.0.0.1`、默认不启动内置 NapCat（由外部 QQ 适配器接入）；
  按 1.4.2 起的入口校验补齐 `data/MaiMBot-host:/MaiMBot/host`、`data/MaiMBot-bots:/MaiMBot/bots` 两个持久化挂载。
- `docker-compose.override.yml` 用宿主机构建出的 `dashboard/dist` 覆盖镜像内预构建产物，便于改前端。
- 镜像标签使用 `<上游版本>-fork.N`，例如 `oh-my-maibot:1.4.8-fork.0`。

### 2. 多模态能力进内核（不再依赖插件）

**Gemini 图片嵌入**：`GeminiClient` 补齐 `image_embedding` 协议，与文本嵌入共用同一套配置、异常与失败快照。

- 不走 google-genai SDK：2.x 的 `embed_content` 只会发 `:batchEmbedContents`，部分网关只登记了 `:embedContent`，
  因此改用 httpx 直发原生 HTTP。
- 鉴权按 `auth_type` 支持 bearer / header / query / none，未配置时回落到官方 `x-goog-api-key`。
- 不写 `request_protocol_hash`，切换后历史图片向量指纹不变，已有记忆不需要重建。

**动图理解**：`src/chat/image_system/animation.py`，GIF / WebP 抽多帧后交给视觉模型描述。

- 用「多帧图片」而不是直接送视频：视觉模型对视频通常按约 1 fps 采样，多帧图没有采样损耗，也不依赖 ffmpeg 的编码路径。
- 抽帧铺白底 PNG，避免透明区域被描述成「黑色背景」。
- 生效位置：图片描述、表情包描述与双维度标签打标、图片记忆入库（入库前转 PNG 首帧封面）。
- 配置在 `visual` 节：`enable_animation_understanding`（默认 `true`）、`animation_max_frames`（默认 `6`，范围 2–16）、
  `animation_max_side`（默认 `512`，范围 128–1024）。
- 配套提示词 `prompts/{zh-CN,en-US,ja-JP}/animation_description.prompt`。

### 3. 表情包

- 上游 1.4.x 已把表情发送从 `send_emoji` 工具改成 reply 的 `attach_emoji` + embedding 双维度匹配，fork 跟随上游，
  **不再维护** `emoji.maisaka.*` 钩子与 `emoji.plugin_selector` 配置。
- fork 保留描述清洗 `_sanitize_emoji_description`：截断正文长度、限制标签长度与数量，避免截屏类表情绕过提示词约束。
- fork 保留出站占位符剥离：模型若把上下文里的 `[表情包: 描述]` 抄进正文，发送前会被剔除；
  若剔除后正文为空，返回 `emoji_placeholder_only` 失败并提示改用 `attach_emoji`。
- `attach_emoji` 支持声明目标情绪（`emotion`），透传到表情选取与视觉回退提示词。

### 4. 诊断日志轮转与调试产物清理

- `logs/plugin_runtime_debug/runner_rpc_debug.jsonl` 由 Host 与 Runner 两个进程共用追加写入，改为按大小轮转
  （`plugin_runtime_debug_max_bytes`，默认 8 MiB；`plugin_runtime_debug_backup_count`，默认 5 份），
  轮转时用文件锁避免两个进程互相覆盖。
- 每日清理 `logs/maisaka_prompt`、`logs/plugin_runtime_debug`、`logs/memory_diagnostics` 中超过
  `debug_artifact_retention_days`（默认 7 天）的文件，总开关 `debug_artifact_cleanup_enabled`（默认 `true`）。
- 手动执行：`python -m src.common.debug_artifacts --logs-root logs --days 7 --apply`（不带 `--apply` 只统计）。

### 5. 依赖管理统一到 uv

- 不保留根目录 `requirements.txt` 与 `src/A_memorix/requirements.txt`，以 `pyproject.toml` + `uv.lock` 为准，
  外加 `.python-version` 固定 Python 3.13。
- `Dockerfile` 依赖层复制 `uv.lock` 并按锁安装，构建可复现；`.dockerignore` 不再排除 `uv.lock`。
- `scripts/run.sh` 使用 `uv pip install -e .`；自更新的依赖变更检测只看 `pyproject.toml` + `uv.lock`。

### 6. 插件自定义页

- `dashboard` 侧放开外链资源（`img` / `font` / `style` 允许 `https:`），`connect-src` 按插件声明的 `network`
  白名单收紧；未声明时回落 `connect-src 'none'`。
- 只接受 `https` 源，禁止裸通配符；`network` 条目数上限 8（`webui_schema.py` 的 fork 自有约束）。

### 7. 其他

- SnowLuma 适配器使用统一数据目录（插件 4.5.2 及以上）。

## ⬆️ 合并上游新版本

```bash
git fetch upstream --tags
git merge vX.Y.Z --no-commit --no-ff     # 先看冲突量再决定
uv lock                                  # 同步 pyproject 变更
docker compose build core                # 有 dashboard 变更时再重编前端
```

经验要点：

- 冲突通常只有 `requirements.txt`（本 fork 已删，直接 `rm`）与 `webui_schema.py`（保留 `network` 字段）。
- 上游改动数据库 schema 时，**先在备份副本上演练迁移**再动线上；`PRAGMA user_version` 可查主库版本。
- 主要冲突面：`gemini_client.py`、`official_configs.py`、`emoji_manager.py`、`image_manager.py`、`utils_model.py`、
  `llm_service.py`、`plugin_runtime/runner/runner_main.py`、`plugin_runtime/host/supervisor.py`、`common/logger.py`、
  `dashboard/src/lib/plugin-*.ts`、`Dockerfile`、`docker-compose.yml`。

---

## 📚 上游资料

- **[麦麦文档](https://docs.maibot.chat)**：最全面的文档中心。
- **[Release](https://github.com/Mai-with-u/MaiBot/releases/)**：上游正式版发布页。
- **[部署教程](https://docs.maibot.chat/manual/)**
- **[麦麦启动器](https://github.com/Mai-with-u/MaiBotOneKey/releases/)**（Windows / macOS 一键包，面向上游源码，本 fork 不适用）

## 👥 贡献者

上游项目的贡献者，本 fork 的全部改动均基于他们的工作：

<a href="https://github.com/MaiM-with-u/MaiBot/graphs/contributors">
  <img alt="contributors" src="https://contrib.rocks/image?repo=MaiM-with-u/MaiBot" />
</a>

## 🤝 开源项目友链

- **[AstrBot](https://github.com/AstrBotDevs/AstrBot)**：优秀的 LLM Agent 项目。
- **[Pallas-Bot](https://github.com/PallasBot/Pallas-Bot)**：以防你不知道牛牛又开始更新了。

## 🙏 特别致谢

- **[萨卡班甲鱼](https://en.wikipedia.org/wiki/Sacabambaspis)**：千石可乐很喜欢的生物。
- **[略nd](https://space.bilibili.com/1344099355)**：为麦麦绘制早期的精美人设。
- **[NapCat](https://github.com/NapNeko/NapCatQQ)**：现代化的基于 NTQQ 的 Bot 协议实现。

## ⭐ Star History

上游仓库的 Star 趋势：

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="https://status.maibot.top/card/stars.svg?theme=night">
  <img src="https://status.maibot.top/card/stars.svg" alt="Star 趋势" width="100%">
</picture>

## ⚠️ 注意事项 & License

> [!IMPORTANT]
> 使用前请阅读上游的 [用户协议 (EULA)](EULA.md) 和 [隐私协议](PRIVACY.md)。AI 生成内容请仔细甄别。

**License**: GPL-3.0（沿用上游）。本 fork 的改动同样以 GPL-3.0 发布。
