"""调试产物清理。

主日志的清理走 ``cleanup_old_logs``，只覆盖 ``logs/*.log*`` 这一层；
Prompt 预览、插件运行时诊断、内存诊断都写在 ``logs/`` 的子目录里，
需要单独按保留天数清理，否则只会被各自的条数上限约束，长期只增不减。
"""

from __future__ import annotations

import argparse
import logging
import os
import time
from pathlib import Path
from typing import Any, Dict, Iterable

logger = logging.getLogger(__name__)

# 只清理确实是诊断产物的目录；表情审核等业务数据不在范围内。
DEBUG_SUBDIRS = ("plugin_runtime_debug", "maisaka_prompt", "memory_diagnostics")
# 预览目录里的图片引用索引是清理逻辑的输入，不能按保留天数删除。
_PROTECTED_PREFIXES = (".image-reference-index",)
# 轮转锁文件被进程持有，删掉会换出新的锁 inode，必须跳过。
_LOCK_SUFFIXES = (".lock",)


def cleanup_debug_artifacts(
    logs_root: Path | str,
    retention_days: int,
    *,
    dry_run: bool = False,
    now: float | None = None,
) -> Dict[str, Any]:
    """删除调试目录中超过保留天数的文件，并回收被清空的会话目录。"""

    root = Path(logs_root)
    cutoff = (now if now is not None else time.time()) - max(1, int(retention_days)) * 86400
    stats: Dict[str, Any] = {
        "deleted_files": 0,
        "freed_bytes": 0,
        "removed_dirs": 0,
        "errors": [],
    }

    for subdir_name in DEBUG_SUBDIRS:
        subdir = root / subdir_name
        if not subdir.is_dir():
            continue
        files, directories = _scan(subdir)
        for path in files:
            if path.name.startswith(_PROTECTED_PREFIXES) or path.name.endswith(_LOCK_SUFFIXES):
                continue
            try:
                file_stat = path.stat()
            except OSError:
                continue
            if file_stat.st_mtime >= cutoff:
                continue
            if not dry_run:
                try:
                    path.unlink()
                except OSError as exc:
                    stats["errors"].append(f"{path}: {exc}")
                    continue
            stats["deleted_files"] += 1
            stats["freed_bytes"] += file_stat.st_size

        if dry_run:
            continue
        # 由深到浅删除空目录，避免把仍有用文件的会话目录连带删掉。
        for directory in sorted(directories, key=lambda item: len(item.parts), reverse=True):
            try:
                if directory.is_dir() and not any(directory.iterdir()):
                    directory.rmdir()
                    stats["removed_dirs"] += 1
            except OSError:
                continue

    return stats


def _scan(directory: Path) -> tuple[list[Path], list[Path]]:
    """一次遍历收集文件与子目录，避免对每层反复 scandir。"""

    files: list[Path] = []
    directories: list[Path] = []
    pending = [directory]
    while pending:
        current = pending.pop()
        try:
            with os.scandir(current) as entries:
                for entry in entries:
                    try:
                        if entry.is_dir(follow_symlinks=False):
                            directories.append(Path(entry.path))
                            pending.append(Path(entry.path))
                        elif entry.is_file(follow_symlinks=False):
                            files.append(Path(entry.path))
                    except OSError:
                        continue
        except OSError as exc:
            logger.warning(f"扫描调试目录失败: {current}: {exc}")
    return files, directories


def cleanup_debug_artifacts_from_config(*, logs_root: Path | str = "logs", dry_run: bool = False) -> Dict[str, Any] | None:
    """按 ``[log]`` 配置执行清理；关闭开关或处于 Runner 子进程时直接跳过。"""

    from src.common import logger as logger_module

    log_config = logger_module.LOG_CONFIG
    if not bool(log_config.get("debug_artifact_cleanup_enabled", True)):
        return None
    # Runner 子进程与主进程共用同一份目录，交给主进程统一清理即可，避免重复扫描。
    if os.environ.get("MAIBOT_RUNNER_GROUP"):
        return None
    retention_days = int(log_config.get("debug_artifact_retention_days", 7) or 7)
    stats = cleanup_debug_artifacts(logs_root, retention_days, dry_run=dry_run)
    if stats["deleted_files"]:
        logger.info(
            f"清理调试产物: 文件={stats['deleted_files']} 目录={stats['removed_dirs']} "
            f"释放={stats['freed_bytes'] / 1024 / 1024:.2f} MB 保留={retention_days}天"
        )
    for error in stats["errors"]:
        logger.warning(f"清理调试产物失败: {error}")
    return stats


def _parse_args(argv: Iterable[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="按保留天数清理 MaiBot 调试产物")
    parser.add_argument("--logs-root", default="logs", help="日志根目录，默认 logs")
    parser.add_argument("--days", type=int, default=7, help="保留天数，默认 7")
    parser.add_argument("--apply", action="store_true", help="真正删除；默认只统计")
    return parser.parse_args(list(argv) if argv is not None else None)


def main(argv: Iterable[str] | None = None) -> int:
    args = _parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    stats = cleanup_debug_artifacts(args.logs_root, args.days, dry_run=not args.apply)
    logger.info(
        f"{'已删除' if args.apply else '将删除'} {stats['deleted_files']} 个文件、"
        f"{stats['removed_dirs']} 个空目录，释放 {stats['freed_bytes'] / 1024 / 1024:.2f} MB"
    )
    return 0 if not stats["errors"] else 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
