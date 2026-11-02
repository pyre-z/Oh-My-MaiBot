"""插件运行时 RPC 调试日志的轮转写入。

Host 与 Runner 是独立进程，共用同一个 JSONL 诊断文件，因此轮转必须加文件锁：
两边同时 rename 会把对方刚写出的备份覆盖掉。日志上限从 ``[log]`` 配置读取，
读取失败时回退到内置默认值，避免诊断设施本身影响业务。
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Mapping

try:  # pragma: no cover - 非 POSIX 平台退化为无锁轮转
    import fcntl
except ImportError:  # pragma: no cover
    fcntl = None  # type: ignore[assignment]

DEFAULT_MAX_BYTES = 8 * 1024 * 1024
DEFAULT_BACKUP_COUNT = 5
_LOCK_SUFFIX = ".lock"


def resolve_debug_limits() -> tuple[int, int]:
    """读取调试日志的单文件上限与备份份数。"""

    try:
        from src.common.logger import LOG_CONFIG

        max_bytes = int(LOG_CONFIG.get("plugin_runtime_debug_max_bytes", DEFAULT_MAX_BYTES) or DEFAULT_MAX_BYTES)
        backup_count = int(LOG_CONFIG.get("plugin_runtime_debug_backup_count", DEFAULT_BACKUP_COUNT) or 0)
    except Exception:  # noqa: BLE001 - 配置异常不能让诊断写入失败
        max_bytes, backup_count = DEFAULT_MAX_BYTES, DEFAULT_BACKUP_COUNT
    return max(64 * 1024, max_bytes), max(0, backup_count)


def append_debug_record(path: Path, record: Mapping[str, Any]) -> None:
    """把一条诊断记录追加到 JSONL 文件，必要时先轮转。"""

    line = json.dumps(dict(record), ensure_ascii=False, separators=(",", ":")) + "\n"
    encoded_size = len(line.encode("utf-8"))
    path.parent.mkdir(parents=True, exist_ok=True)
    max_bytes, backup_count = resolve_debug_limits()
    rotate_if_needed(path, max_bytes, backup_count, incoming_bytes=encoded_size)
    with open(path, "a", encoding="utf-8") as handle:
        handle.write(line)


def rotate_if_needed(
    path: Path,
    max_bytes: int,
    backup_count: int,
    *,
    incoming_bytes: int = 0,
) -> None:
    """当前文件写入后会超过上限时轮转：``.1`` 最新，序号越大越旧。"""

    if not _would_exceed(path, max_bytes, incoming_bytes):
        return

    lock_path = path.with_name(path.name + _LOCK_SUFFIX)
    with open(lock_path, "a+", encoding="utf-8") as lock_handle:
        if fcntl is not None:
            fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX)
        try:
            # 拿到锁后重新确认，另一个进程可能刚刚完成轮转。
            if not _would_exceed(path, max_bytes, incoming_bytes):
                return
            if backup_count <= 0:
                path.unlink(missing_ok=True)
                return
            path.with_name(f"{path.name}.{backup_count}").unlink(missing_ok=True)
            for index in range(backup_count - 1, 0, -1):
                source = path.with_name(f"{path.name}.{index}")
                if source.exists():
                    os.replace(source, path.with_name(f"{path.name}.{index + 1}"))
            os.replace(path, path.with_name(f"{path.name}.1"))
        finally:
            if fcntl is not None:
                fcntl.flock(lock_handle.fileno(), fcntl.LOCK_UN)


def _would_exceed(path: Path, max_bytes: int, incoming_bytes: int) -> bool:
    """判断本次写入是否会把文件顶过上限；空文件不轮转，避免单条超长记录死循环。"""

    try:
        current_size = path.stat().st_size
    except OSError:
        return False
    if current_size <= 0:
        return False
    return current_size + incoming_bytes > max_bytes
