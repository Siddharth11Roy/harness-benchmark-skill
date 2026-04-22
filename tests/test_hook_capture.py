from __future__ import annotations
import io
import json
import sys
from pathlib import Path

import harness.hook_capture as hook


def run_hook(tmp_path: Path, payload: dict, monkeypatch) -> list:
    """Invoke the hook with a mocked stdin and isolated cwd."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(payload)))
    # Re-point the module globals at the new cwd
    monkeypatch.setattr(hook, "LOG_DIR", Path("agent_logs"))
    monkeypatch.setattr(hook, "TOOL_CALLS_FILE", Path("agent_logs/tool_calls.json"))
    hook.main()
    f = Path("agent_logs/tool_calls.json")
    return json.loads(f.read_text()) if f.exists() else []


def test_hook_noop_if_no_agent_logs_dir(tmp_path: Path, monkeypatch):
    """Hook must be silent when agent_logs/ doesn't exist."""
    result = run_hook(tmp_path, {"tool_name": "Read"}, monkeypatch)
    assert result == []  # file doesn't exist


def test_hook_appends_success(tmp_path: Path, monkeypatch):
    (tmp_path / "agent_logs").mkdir()
    (tmp_path / "agent_logs" / "tool_calls.json").write_text("[]", encoding="utf-8")
    result = run_hook(tmp_path, {
        "tool_name": "Write",
        "tool_input": {"file_path": "hello.py"},
        "tool_response": {"filePath": "hello.py"},
    }, monkeypatch)
    assert len(result) == 1
    assert result[0]["tool"] == "Write"
    assert result[0]["success"] is True
    assert result[0]["input"] == "hello.py"


def test_hook_detects_error(tmp_path: Path, monkeypatch):
    (tmp_path / "agent_logs").mkdir()
    (tmp_path / "agent_logs" / "tool_calls.json").write_text("[]", encoding="utf-8")
    result = run_hook(tmp_path, {
        "tool_name": "Bash",
        "tool_input": {"command": "false"},
        "tool_response": {"error": "nonzero exit"},
    }, monkeypatch)
    assert result[0]["success"] is False


def test_hook_corrupt_file_recovers(tmp_path: Path, monkeypatch):
    """If tool_calls.json is corrupt, hook should not crash — it should overwrite."""
    (tmp_path / "agent_logs").mkdir()
    (tmp_path / "agent_logs" / "tool_calls.json").write_text("{not json", encoding="utf-8")
    result = run_hook(tmp_path, {
        "tool_name": "Read",
        "tool_input": {"file_path": "x.py"},
        "tool_response": {"content": "ok"},
    }, monkeypatch)
    assert len(result) == 1
    assert result[0]["tool"] == "Read"
