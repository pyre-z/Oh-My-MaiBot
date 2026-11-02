# Oh-My-MaiBot

本仓库是 [MaiBot](https://github.com/Mai-with-u/MaiBot) 的个人 fork，仅供本地部署与自用改动使用。

- 上游仓库：<https://github.com/Mai-with-u/MaiBot>
- 上游文档：<https://docs.mai-mai.org>
- 同步基线：MaiBot 1.3.19
- 本 fork 的改动：`git log --oneline origin/main..main`

安装、配置、插件与使用方法请以[上游文档](https://docs.mai-mai.org)为准；Issue 和 PR 请优先提交到上游仓库。

## 相比上游的改动

### 1. 本地部署适配

- `Dockerfile` 内置 `ffmpeg` / `ffprobe`，动图抽帧等能力开箱可用。
- `docker-compose.yml` 改为本地 `build` 镜像、端口只绑 `127.0.0.1`、默认不启动内置 NapCat（由外部 QQ 适配器接入）。
- 细化 `send_emoji` 内置工具的描述，减少模型误调用。

### 2. 多模态能力进内核（不再依赖插件）

这两项原来分别靠 `pyre-z.image-embed`、`pyre.gif-vision` 两个插件实现，现在由内核直接承担，插件可以关闭。

**Gemini 图片嵌入**：`GeminiClient` 补齐 `image_embedding` 协议，与文本嵌入共用同一套配置、异常与失败快照。

- 不走 google-genai SDK：2.x 的 `embed_content` 只会发 `:batchEmbedContents`，部分网关只登记了 `:embedContent`，因此改用 httpx 直发原生 HTTP，请求体与 `inline_data` 约定保持一致。
- 鉴权按 `auth_type` 支持 bearer / header / query / none，未配置时回落到官方 `x-goog-api-key`。
- 不写 `request_protocol_hash`，切换后历史图片向量指纹不变，已有记忆不需要重建。

**动图理解**：新增 `src/chat/image_system/animation.py`，GIF / WebP 抽多帧后交给视觉模型描述。

- 用「多帧图片」而不是直接送视频：视觉模型对视频通常按约 1 fps 采样，多帧图没有采样损耗，也不依赖 ffmpeg 的编码路径。
- 抽帧铺白底 PNG，避免透明区域被描述成「黑色背景」。
- 生效位置：图片描述、表情包打标、图片记忆入库（入库前转 PNG 首帧封面）。描述按原文件哈希缓存。
- 配置在 `visual` 节：`enable_animation_understanding`（默认 `true`）、`animation_max_frames`（默认 `6`，范围 2–16）、`animation_max_side`（默认 `512`，范围 128–1024）。
- 配套提示词 `prompts/{zh-CN,en-US,ja-JP}/animation_description.prompt`。

### 3. 表情包选图交给插件

- 新增 Hook `emoji.maisaka.select`：`send_emoji` 在采样拼图前先问插件要哈希，拿到就跳过「随机抽 N 张 + 视觉子代理选图」，拿不到自动回退原流程。
- 新增配置 `emoji.plugin_selector`（默认 `true`）：关掉即恢复内核原有的视觉选图。
- 用途：把选择权交给语义召回插件（描述向量 + 可选模型重排 + 前 N 随机），省掉每轮一次 25 图视觉调用。

### 4. 依赖管理统一到 uv

- 删除 `requirements.txt` 与 `src/A_memorix/requirements.txt`，只保留 `pyproject.toml` + `uv.lock`（外加 `.python-version` 固定 Python 3.13）。
- `Dockerfile` 依赖层复制 `uv.lock` 并按锁安装，构建可复现；`.dockerignore` 不再排除 `uv.lock`。
- `scripts/run.sh` 的 `pip install -r` 改为 `uv pip install -e .`。
- 自更新的依赖变更检测从 `requirements.txt` 改为 `pyproject.toml` + `uv.lock`，只走 `uv sync`。

### 5. 其他

- 移除过时的 SnowLuma 适配器数据目录挂载，插件改用统一数据目录（配合适配器 4.5.2 及以上）。
- 修正表情包占位文案相关的陈旧测试断言（`pytests/message_test/session_message_test.py::test_emoji`）。

> 改动集中在上述文件，上游其余代码保持原样。合并上游新版本时，`gemini_client.py`、`official_configs.py`、`emoji_manager.py`、`image_manager.py`、`utils_model.py`、`llm_service.py`、`builtin_tool/send_emoji.py`、`Dockerfile`、`docker-compose.yml` 是主要冲突面。

## 本地开发与运行

依赖与虚拟环境统一由 [uv](https://docs.astral.sh/uv/) 管理：

```bash
uv sync               # 按 uv.lock 创建 .venv 并安装依赖
uv run python bot.py  # 在项目虚拟环境中启动
```

改了依赖后执行 `uv lock` 更新 `uv.lock` 再提交。

**License**: GPL-3.0（沿用上游）
