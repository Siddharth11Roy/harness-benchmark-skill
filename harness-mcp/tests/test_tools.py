from pathlib import Path

import pytest

from harness_mcp import tools
from harness_mcp.store import SessionStore

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def store():
    return SessionStore(root=FIXTURES)


def test_list_sessions(store):
    out = tools.list_sessions(store)
    assert out["count"] >= 1
    assert any(s["id"] == "sample_session" for s in out["sessions"])


def test_get_session(store):
    out = tools.get_session(store, "sample_session")
    assert out["session"]["id"] == "sample_session"
    assert out["step_count"] == 3
    assert out["tool_call_count"] == 4
    assert "score" in out and "metrics" in out["score"]


def test_get_score(store):
    out = tools.get_score(store, "sample_session")
    assert "composite" in out["metrics"]


def test_get_trace_with_limit(store):
    out = tools.get_trace(store, "sample_session", limit=2)
    assert out["total"] == 3
    assert len(out["trace"]) == 2


def test_get_tool_calls_only_failed(store):
    out = tools.get_tool_calls(store, "sample_session", only_failed=True)
    assert out["total"] == 0


def test_get_diffs(store):
    out = tools.get_diffs(store, "sample_session")
    assert out["total"] == 3


def test_get_dashboard_url(store):
    out = tools.get_dashboard_url(store, port=3737)
    assert out["url"] == "http://127.0.0.1:3737"


def test_unknown_session_raises_value_error(store):
    with pytest.raises(ValueError, match="Unknown session"):
        tools.get_score(store, "nope")


def test_refresh_then_use(tmp_path):
    """Re-access flow: Claude can refresh and immediately query the new session."""
    store = SessionStore(root=tmp_path)
    assert tools.list_sessions(store)["count"] == 0

    new_logs = tmp_path / "later_run" / "agent_logs"
    new_logs.mkdir(parents=True)
    src = FIXTURES / "sample_session" / "agent_logs"
    for f in ("trace.md", "tool_calls.json", "diff_summary.md", "session_meta.json"):
        (new_logs / f).write_text((src / f).read_text(encoding="utf-8"), encoding="utf-8")

    refreshed = tools.refresh(store)
    assert refreshed["count"] == 1
    assert tools.get_session(store, "later_run")["step_count"] == 3
