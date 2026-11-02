import json
from pathlib import Path

from src.plugin_runtime import debug_log


def _append(path: Path, index: int) -> None:
    debug_log.append_debug_record(path, {"event": "test", "index": index, "padding": "x" * 200})


def test_rotation_keeps_latest_backups(tmp_path: Path, monkeypatch) -> None:
    debug_file = tmp_path / "logs" / "plugin_runtime_debug" / "runner_rpc_debug.jsonl"
    monkeypatch.setattr(debug_log, "resolve_debug_limits", lambda: (2 * 1024, 3))

    for index in range(60):
        _append(debug_file, index)

    assert debug_file.exists()
    assert debug_file.stat().st_size <= 2 * 1024
    backups = sorted(
        path.name for path in debug_file.parent.glob("runner_rpc_debug.jsonl.[0-9]*")
    )
    assert backups == [
        "runner_rpc_debug.jsonl.1",
        "runner_rpc_debug.jsonl.2",
        "runner_rpc_debug.jsonl.3",
    ]
    records = [json.loads(line) for line in debug_file.read_text(encoding="utf-8").splitlines()]
    assert records[-1]["index"] == 59


def test_rotation_without_backups_truncates(tmp_path: Path, monkeypatch) -> None:
    debug_file = tmp_path / "runner_rpc_debug.jsonl"
    monkeypatch.setattr(debug_log, "resolve_debug_limits", lambda: (1024, 0))

    for index in range(30):
        _append(debug_file, index)

    assert debug_file.exists()
    assert debug_file.stat().st_size < 1024
    assert not list(debug_file.parent.glob("runner_rpc_debug.jsonl.*[0-9]"))


def test_oversized_single_record_does_not_loop(tmp_path: Path, monkeypatch) -> None:
    debug_file = tmp_path / "runner_rpc_debug.jsonl"
    monkeypatch.setattr(debug_log, "resolve_debug_limits", lambda: (1024, 2))

    debug_log.append_debug_record(debug_file, {"event": "huge", "padding": "x" * 2048})
    debug_log.append_debug_record(debug_file, {"event": "next"})

    # 单条记录本身超过上限时允许原样写入，下一次写入把它轮转走，不能反复轮转空文件。
    assert json.loads(debug_file.read_text(encoding="utf-8"))["event"] == "next"
    rotated = json.loads((debug_file.parent / "runner_rpc_debug.jsonl.1").read_text(encoding="utf-8"))
    assert rotated["event"] == "huge"
