import os
import time
from pathlib import Path

from src.common.debug_artifacts import cleanup_debug_artifacts


def _write(path: Path, content: str, *, age_days: float) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    timestamp = time.time() - age_days * 86400
    os.utime(path, (timestamp, timestamp))


def test_cleanup_deletes_expired_artifacts_and_keeps_protected_files(tmp_path: Path) -> None:
    root = tmp_path / "logs"
    expired_preview = root / "maisaka_prompt" / "group_1" / "preview.json"
    fresh_preview = root / "maisaka_prompt" / "group_1" / "fresh.json"
    index_file = root / "maisaka_prompt" / ".image-reference-index.sqlite3"
    lock_file = root / "plugin_runtime_debug" / "runner_rpc_debug.jsonl.lock"
    expired_debug = root / "plugin_runtime_debug" / "runner_rpc_debug.jsonl.1"
    expired_memory = root / "memory_diagnostics" / "memory.jsonl.2"
    unrelated = root / "expression_review" / "review_logs.json"

    _write(expired_preview, "{}", age_days=10)
    _write(fresh_preview, "{}", age_days=1)
    _write(index_file, "index", age_days=10)
    _write(lock_file, "", age_days=10)
    _write(expired_debug, "{}", age_days=10)
    _write(expired_memory, "{}", age_days=10)
    _write(unrelated, "{}", age_days=10)
    # 会话目录里只剩过期文件时，删除后目录应一并回收。
    empty_after = root / "maisaka_prompt" / "group_2" / "old.json"
    _write(empty_after, "{}", age_days=10)

    stats = cleanup_debug_artifacts(root, 7)

    assert stats["deleted_files"] == 4
    assert not expired_preview.exists()
    assert not expired_debug.exists()
    assert not expired_memory.exists()
    assert not empty_after.parent.exists()
    assert fresh_preview.exists()
    assert index_file.exists()
    assert lock_file.exists()
    assert unrelated.exists()
    assert stats["removed_dirs"] == 1
    assert stats["errors"] == []


def test_cleanup_dry_run_reports_without_deleting(tmp_path: Path) -> None:
    root = tmp_path / "logs"
    expired = root / "plugin_runtime_debug" / "runner_rpc_debug.jsonl.3"
    _write(expired, "x" * 128, age_days=30)

    stats = cleanup_debug_artifacts(root, 7, dry_run=True)

    assert stats["deleted_files"] == 1
    assert stats["freed_bytes"] == 128
    assert expired.exists()
