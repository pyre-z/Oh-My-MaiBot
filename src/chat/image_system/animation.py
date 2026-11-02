"""动图理解：GIF / 动画 WebP 抽帧后一次性交给视觉模型。

为什么不用「动图 → MP4 → 视频输入」：实测视觉模型对视频按约 1 fps 采样，
10 帧 × 0.4 秒的视频只能读出第 2、4、7、9 帧，必须把每帧拉长到 1 秒才能保证
每一帧都被看到。直接把抽出来的帧当多张图片按顺序发过去，既没有采样损耗，
也不依赖 ffmpeg，OpenAI 兼容通道同样可用。

抽帧数、单帧尺寸与总开关都在 `visual` 配置节（`enable_animation_understanding`
/ `animation_max_frames` / `animation_max_side`）。
"""

from __future__ import annotations

import asyncio
import base64
import io
from typing import List, Optional

from src.common.logger import get_logger
from src.config.config import global_config
from src.prompt.prompt_manager import prompt_manager
from src.services.llm_service import LLMServiceClient

logger = get_logger("animation")

ANIMATED_FORMATS = frozenset({"gif", "webp"})
"""可能是动图的容器格式；是否多帧由 Pillow 的帧数判定。"""

DEFAULT_ANIMATION_PROMPT = (
    "这是一张动图按时间顺序均匀抽取的 {frame_count} 帧。请连贯地描述动图里发生的动作与变化，"
    "如果有文字请概括，输出为一段平文本，最多 200 字，不要分点，不要逐帧罗列。"
)
"""内置提示词：自定义提示词 `animation_description` 缺失时使用。"""

_animation_vlm = LLMServiceClient(task_name="vlm", request_type="image.animation")


def animation_enabled() -> bool:
    """动图理解总开关（`visual.enable_animation_understanding`）。"""

    try:
        return bool(global_config.visual.enable_animation_understanding)
    except Exception:  # noqa: BLE001 - 配置缺失时按开启处理，保持与默认值一致
        return True


def detect_animated_format(image_bytes: bytes) -> str:
    """判定是否为多帧动图，是则返回格式名（`gif` / `webp`），否则返回空串。

    Args:
        image_bytes: 原始图片字节。

    Returns:
        str: 动图格式名，或空串。
    """

    if not image_bytes:
        return ""
    try:
        from PIL import Image

        with Image.open(io.BytesIO(image_bytes)) as image:
            image_format = str(image.format or "").lower()
            if image_format not in ANIMATED_FORMATS:
                return ""
            frames = int(getattr(image, "n_frames", 1) or 1)
            if frames <= 1 or not bool(getattr(image, "is_animated", False)):
                return ""
            return image_format
    except Exception:  # noqa: BLE001 - 解不开就按静态图处理
        return ""


def _frame_limit(max_frames: Optional[int]) -> int:
    """解析抽帧上限：显式参数 > 配置 > 默认 6。"""

    if max_frames is not None and int(max_frames) >= 2:
        return int(max_frames)
    try:
        configured = int(global_config.visual.animation_max_frames)
    except Exception:  # noqa: BLE001
        configured = 6
    return max(2, min(16, configured))


def _max_side(max_side: Optional[int]) -> int:
    """解析单帧长边上限：显式参数 > 配置 > 默认 512。"""

    if max_side is not None and int(max_side) > 0:
        return int(max_side)
    try:
        configured = int(global_config.visual.animation_max_side)
    except Exception:  # noqa: BLE001
        configured = 512
    return max(128, min(1024, configured))


def extract_frames(
    image_bytes: bytes,
    *,
    max_frames: Optional[int] = None,
    max_side: Optional[int] = None,
) -> List[bytes]:
    """均匀抽取若干帧，统一转成白底 PNG（按时间顺序）。

    Args:
        image_bytes: 动图字节。
        max_frames: 最多抽多少帧。
        max_side: 单帧长边上限（像素）。

    Returns:
        List[bytes]: PNG 帧字节列表；不是多帧动图时返回空列表。

    Raises:
        ValueError: 不是多帧动图。
    """

    from PIL import Image, ImageSequence

    limit = _frame_limit(max_frames)
    side = _max_side(max_side)

    with Image.open(io.BytesIO(image_bytes)) as image:
        total = int(getattr(image, "n_frames", 1) or 1)
        if total < 2:
            raise ValueError("不是多帧动图（只有 1 帧）")
        target = max(2, min(limit, total))
        if target >= total:
            indices = list(range(total))
        else:
            step = (total - 1) / (target - 1)
            indices = sorted({int(round(index * step)) for index in range(target)})
        wanted = set(indices)

        frames: List[bytes] = []
        for index, frame in enumerate(ImageSequence.Iterator(image)):
            if index not in wanted:
                continue
            canvas = frame.convert("RGBA")
            # 透明动图铺白底：大多数表情包按浅色背景设计，黑底会让描述偏向「黑色背景」。
            background = Image.new("RGB", canvas.size, (255, 255, 255))
            background.paste(canvas, mask=canvas.split()[-1])
            if max(background.size) > side:
                background.thumbnail((side, side))
            buffer = io.BytesIO()
            background.save(buffer, format="PNG")
            frames.append(buffer.getvalue())
        return frames


def to_static_cover(image_bytes: bytes, *, max_side: int = 640, max_bytes: int = 4 * 1024 * 1024) -> bytes:
    """把动图首帧转成 PNG，用于只接受静态格式的图片记忆入库。

    Args:
        image_bytes: 动图字节。
        max_side: 长边上限（像素）。
        max_bytes: 输出体积上限（字节）。

    Returns:
        bytes: PNG 字节；非动图或转换失败返回空字节（调用方保留原图）。
    """

    if not detect_animated_format(image_bytes):
        return b""

    from PIL import Image

    try:
        with Image.open(io.BytesIO(image_bytes)) as image:
            image.seek(0)
            has_alpha = image.mode in {"RGBA", "LA", "PA"} or "transparency" in image.info
            frame = image.convert("RGBA" if has_alpha else "RGB")
    except Exception:  # noqa: BLE001 - 解不开就交给调用方保留原图
        return b""

    side = max(128, int(max_side))
    for _attempt in range(6):
        candidate = frame.copy()
        candidate.thumbnail((side, side))
        buffer = io.BytesIO()
        try:
            candidate.save(buffer, format="PNG", optimize=True)
        except Exception:  # noqa: BLE001
            return b""
        payload = buffer.getvalue()
        if len(payload) <= max_bytes:
            return payload
        if side <= 128:
            break
        side = max(128, int(side * 0.75))
    return b""


async def _render_prompt(frame_count: int) -> str:
    """渲染动图描述提示词：优先自定义 `animation_description`，缺失时用内置文本。"""

    try:
        template = prompt_manager.get_prompt("animation_description")
        template.add_context("frame_count", str(frame_count))
        prompt = await prompt_manager.render_prompt(template)
        if str(prompt or "").strip():
            return str(prompt).strip()
    except Exception as exc:  # noqa: BLE001 - 自定义提示词缺失/渲染失败都退回内置
        logger.debug(f"读取 animation_description 提示词失败，使用内置文本: {exc}")
    return DEFAULT_ANIMATION_PROMPT.format(frame_count=frame_count)


async def describe_animation(
    image_bytes: bytes,
    *,
    max_frames: Optional[int] = None,
    max_side: Optional[int] = None,
    session_id: str = "",
) -> str:
    """抽帧并生成动图描述。

    Args:
        image_bytes: 动图字节。
        max_frames: 抽帧上限，默认读配置。
        max_side: 单帧长边上限，默认读配置。
        session_id: 会话标识，仅用于统计归属。

    Returns:
        str: 一句话描述；失败或未启用时返回空串。
    """

    if not animation_enabled():
        return ""

    frames = await asyncio.to_thread(extract_frames, image_bytes, max_frames=max_frames, max_side=max_side)
    if not frames:
        return ""

    try:
        max_images = int(global_config.visual.max_image_num)
    except Exception:  # noqa: BLE001
        max_images = 64
    if max_images >= 2:
        frames = frames[:max_images]

    prompt = await _render_prompt(len(frames))
    try:
        result = await _animation_vlm.generate_response_for_frames(
            prompt,
            [(base64.b64encode(frame).decode("ascii"), "png") for frame in frames],
            session_id=session_id,
        )
    except Exception as exc:  # noqa: BLE001 - 单张动图失败不影响消息链路
        logger.warning(f"动图描述生成失败: {exc}")
        return ""

    description = str(result.response or "").strip()
    if not description:
        logger.warning("动图描述为空")
    return description
