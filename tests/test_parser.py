from __future__ import annotations
import json
import pytest
from pathlib import Path

from harness.parser import (
    parse_trace, parse_tool_calls, parse_diff_summary, parse_session_meta,
    load_logs, detect_wasted,
)
from harness.schemas import DiffEntry
from harness.constants import (
    HarnessVersionError, HarnessSizeError, MAX_FILE_BYTES,
)


# ---------- trace.md ----------
def test_parse_trace_basic(tmp_path: Path):
    content = """# Trace
---
STEP: 1
GOAL:
Build something
FILES READ:
- a.py
- b.py
FILES MODIFIED:
- c.py
TOOLS USED:
- Write
DECISION:
Looks good
RESULT:
Done
NEXT PLAN:
Continue
---
"""
    f = tmp_path / "trace.md"
    f.write_text(content, encoding="utf-8")
    steps = parse_trace(f)
    assert len(steps) == 1
    assert steps[0].step == 1
    assert steps[0].goal == "Build something"
    assert steps[0].files_read == ["a.py", "b.py"]
    assert steps[0].files_modified == ["c.py"]
    assert steps[0].phase == "BUILD"


def test_parse_trace_detects_failed(tmp_path: Path):
    content = """---
STEP: 1
GOAL:
Attempt X
RESULT:
Streamlit abandoned after timeout
---
"""
    f = tmp_path / "trace.md"
    f.write_text(content, encoding="utf-8")
    steps = parse_trace(f)
    assert steps[0].phase == "FAILED"


def test_parse_trace_skips_none_entries(tmp_path: Path):
    content = """---
STEP: 1
GOAL:
Something
FILES READ:
None
---
"""
    f = tmp_path / "trace.md"
    f.write_text(content, encoding="utf-8")
    steps = parse_trace(f)
    assert steps[0].files_read == []


# ---------- tool_calls.json ----------
def test_parse_tool_calls_inferred_failure(tmp_path: Path):
    data = [
        {"step": 1, "tool": "Bash", "input": "x", "output_summary": "ok"},
        {"step": 1, "tool": "Bash", "input": "x", "output_summary": "ImportError"},
    ]
    f = tmp_path / "tool_calls.json"
    f.write_text(json.dumps(data), encoding="utf-8")
    calls = parse_tool_calls(f)
    assert calls[0].success is True
    assert calls[1].success is False


def test_parse_tool_calls_explicit_success_wins(tmp_path: Path):
    """Explicit success field overrides keyword inference."""
    data = [{"step": 1, "tool": "Bash", "output_summary": "error", "success": True}]
    f = tmp_path / "tool_calls.json"
    f.write_text(json.dumps(data), encoding="utf-8")
    calls = parse_tool_calls(f)
    assert calls[0].success is True


def test_parse_tool_calls_versioned_envelope(tmp_path: Path):
    data = {"harness_version": "1.0", "calls": [{"step": 1, "tool": "Read"}]}
    f = tmp_path / "tool_calls.json"
    f.write_text(json.dumps(data), encoding="utf-8")
    calls = parse_tool_calls(f)
    assert len(calls) == 1


# ---------- diff_summary.md ----------
def test_parse_diff_basic(tmp_path: Path):
    content = """# Diff
---
STEP: 1
FILES CHANGED: a.py, b.py
LINES ADDED: 10
LINES REMOVED: 2
REASON FOR CHANGE: Initial commit
---
"""
    f = tmp_path / "diff_summary.md"
    f.write_text(content, encoding="utf-8")
    diffs = parse_diff_summary(f)
    assert len(diffs) == 1
    assert diffs[0].files_changed == ["a.py", "b.py"]
    assert diffs[0].lines_added == 10
    assert diffs[0].lines_removed == 2


def test_wasted_detection_structural_false_positive_fix(tmp_path: Path):
    """Regression: 'removed deprecated param' used to be flagged as wasted.
    Structural detection (DELETED marker) must NOT flag it."""
    content = """---
STEP: 1
FILES CHANGED: cleaner.py
LINES ADDED: 2
LINES REMOVED: 2
REASON FOR CHANGE: Removed deprecated infer_datetime_format parameter.
---
"""
    f = tmp_path / "diff_summary.md"
    f.write_text(content, encoding="utf-8")
    diffs = parse_diff_summary(f)
    assert diffs[0].is_wasted is False


def test_wasted_detection_structural_true_positive(tmp_path: Path):
    """A file marked (DELETED) causes all diffs touching it to be wasted."""
    content = """---
STEP: 1
FILES CHANGED: gui.py (NEW)
LINES ADDED: 500
LINES REMOVED: 0
REASON FOR CHANGE: Built streamlit gui
---
STEP: 2
FILES CHANGED: gui.py (DELETED)
LINES ADDED: 0
LINES REMOVED: 500
REASON FOR CHANGE: Pivoted to React, deleted streamlit.
---
"""
    f = tmp_path / "diff_summary.md"
    f.write_text(content, encoding="utf-8")
    diffs = parse_diff_summary(f)
    assert diffs[0].is_wasted is True
    assert diffs[1].is_wasted is True
    assert diffs[1].is_intentional_pivot is True


def test_detect_wasted_unit():
    entries = [
        DiffEntry(step=1, files_changed=["x.py (NEW)"], lines_added=10, reason="add"),
        DiffEntry(step=2, files_changed=["x.py (DELETED)"], lines_removed=10, reason="pivot"),
    ]
    detect_wasted(entries)
    assert all(e.is_wasted for e in entries)
    assert entries[1].is_intentional_pivot is True


# ---------- session_meta.json ----------
def test_meta_missing_is_ok(tmp_path: Path):
    meta = parse_session_meta(tmp_path / "does_not_exist.json")
    assert meta.model == "unknown"


def test_meta_version_mismatch_rejected(tmp_path: Path):
    data = {"harness_version": "2.0", "model": "x"}
    f = tmp_path / "session_meta.json"
    f.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(HarnessVersionError):
        parse_session_meta(f)


def test_meta_version_compatible_accepted(tmp_path: Path):
    data = {"harness_version": "1.5", "model": "x"}  # same major
    f = tmp_path / "session_meta.json"
    f.write_text(json.dumps(data), encoding="utf-8")
    meta = parse_session_meta(f)
    assert meta.model == "x"


def test_meta_invalid_version_rejected(tmp_path: Path):
    data = {"harness_version": "not-a-version"}
    f = tmp_path / "session_meta.json"
    f.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(HarnessVersionError):
        parse_session_meta(f)


def test_meta_interventions_normalized(tmp_path: Path):
    data = {
        "harness_version": "1.0",
        "user_interventions": [
            {"step": 1, "prompt": "stop", "type": "negative"},
            {"step": 2, "prompt": "bad-type", "type": "weird"},  # normalized to negative
        ],
    }
    f = tmp_path / "session_meta.json"
    f.write_text(json.dumps(data), encoding="utf-8")
    meta = parse_session_meta(f)
    assert meta.user_interventions[0].type == "negative"
    assert meta.user_interventions[1].type == "negative"


# ---------- Resource limits ----------
def test_size_cap_enforced(tmp_path: Path, monkeypatch):
    from harness import parser as parser_module
    f = tmp_path / "trace.md"
    f.write_text("x" * 1024, encoding="utf-8")
    monkeypatch.setattr(parser_module, "MAX_FILE_BYTES", 100)
    with pytest.raises(HarnessSizeError):
        parse_trace(f)


def test_field_truncation_caps_huge_input(tmp_path: Path):
    """A pathological huge single field should be truncated, not OOM."""
    huge = "x" * 500_000
    content = f"---\nSTEP: 1\nGOAL:\n{huge}\n---\n"
    f = tmp_path / "trace.md"
    f.write_text(content, encoding="utf-8")
    steps = parse_trace(f)
    assert len(steps[0].goal) <= 120_000  # truncation budget + margin


# ---------- load_logs integration ----------
def test_load_logs_full(write_logs):
    d = write_logs(
        trace_md="---\nSTEP: 1\nGOAL:\nBuild\nRESULT:\nDone\n---\n",
        calls=[{"step": 1, "tool": "Write"}],
        diffs_md="---\nSTEP: 1\nFILES CHANGED: a.py\nLINES ADDED: 5\nLINES REMOVED: 0\nREASON FOR CHANGE: add\n---\n",
        meta={"harness_version": "1.0", "model": "test", "project": "p"},
    )
    inp = load_logs(d)
    assert len(inp.trace) == 1
    assert len(inp.tool_calls) == 1
    assert len(inp.diffs) == 1
    assert inp.meta.model == "test"
