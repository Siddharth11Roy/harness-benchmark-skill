from pathlib import Path

import pytest

from harness_mcp.store import SessionStore

FIXTURES = Path(__file__).parent / "fixtures"


def test_discovers_nested_session():
    store = SessionStore(root=FIXTURES)
    sessions = store.list_sessions()
    assert any(s.id == "sample_session" for s in sessions)


def test_discovers_root_as_logs_dir():
    """If the root itself contains the four log files, it counts as one session."""
    logs = FIXTURES / "sample_session" / "agent_logs"
    store = SessionStore(root=logs)
    sessions = store.list_sessions()
    assert len(sessions) == 1
    assert sessions[0].id == "sample_session"


def test_meta_is_populated():
    store = SessionStore(root=FIXTURES)
    sess = store.get("sample_session")
    assert sess.model == "claude-opus-4-7"
    assert sess.date == "2026-04-22"


def test_load_returns_parsed_input():
    store = SessionStore(root=FIXTURES)
    data = store.load("sample_session")
    assert len(data.trace) == 3
    assert len(data.tool_calls) == 4
    assert len(data.diffs) == 3


def test_score_returns_result():
    store = SessionStore(root=FIXTURES)
    result = store.score("sample_session")
    assert 0.0 <= result.score <= 1.0
    assert result.grade in ("A", "B+", "B", "C", "D")
    assert result.total_steps == 3


def test_unknown_session_raises():
    store = SessionStore(root=FIXTURES)
    with pytest.raises(KeyError):
        store.load("does_not_exist")


def test_refresh_picks_up_new_session(tmp_path):
    store = SessionStore(root=tmp_path)
    assert store.list_sessions() == []

    new_logs = tmp_path / "fresh" / "agent_logs"
    new_logs.mkdir(parents=True)
    src = FIXTURES / "sample_session" / "agent_logs"
    for f in ("trace.md", "tool_calls.json", "diff_summary.md", "session_meta.json"):
        (new_logs / f).write_text((src / f).read_text(encoding="utf-8"), encoding="utf-8")

    sessions = store.refresh()
    assert any(s.id == "fresh" for s in sessions)
