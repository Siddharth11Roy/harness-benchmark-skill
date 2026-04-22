from __future__ import annotations
import json
from pathlib import Path
import pytest

from harness.schemas import (
    HarnessInput, TraceStep, ToolCall, DiffEntry, SessionMeta, UserIntervention,
)


@pytest.fixture
def empty_input() -> HarnessInput:
    return HarnessInput(trace=[], tool_calls=[], diffs=[], meta=SessionMeta())


@pytest.fixture
def clean_input() -> HarnessInput:
    """5 successful steps, no failures, no waste, balanced reads/writes."""
    trace = [TraceStep(step=i, goal=f"step {i}", result="done", phase="BUILD") for i in range(1, 6)]
    tool_calls = []
    for i in range(1, 6):
        tool_calls.append(ToolCall(step=i, tool="Read", input="x", output_summary="ok", success=True))
        tool_calls.append(ToolCall(step=i, tool="Write", input="x", output_summary="ok", success=True))
    diffs = [
        DiffEntry(step=i, files_changed=[f"f{i}.py"], lines_added=10, lines_removed=0, reason="add")
        for i in range(1, 6)
    ]
    return HarnessInput(trace=trace, tool_calls=tool_calls, diffs=diffs, meta=SessionMeta())


@pytest.fixture
def write_logs(tmp_path: Path):
    """Factory: write the 4 log files to a tmp dir."""
    def _write(trace_md: str, calls: list | dict, diffs_md: str, meta: dict | None = None) -> Path:
        d = tmp_path / "agent_logs"
        d.mkdir()
        (d / "trace.md").write_text(trace_md, encoding="utf-8")
        (d / "tool_calls.json").write_text(json.dumps(calls), encoding="utf-8")
        (d / "diff_summary.md").write_text(diffs_md, encoding="utf-8")
        if meta is not None:
            (d / "session_meta.json").write_text(json.dumps(meta), encoding="utf-8")
        return d
    return _write
