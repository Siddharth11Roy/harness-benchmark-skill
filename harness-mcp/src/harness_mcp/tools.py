"""Pure-function MCP tool implementations.

Kept free of MCP SDK types so they're trivial to unit test. The MCP server
in server.py is a thin adapter that calls these.
"""
from __future__ import annotations

from typing import Any

from .store import SessionStore


def list_sessions(store: SessionStore) -> dict[str, Any]:
    sessions = store.list_sessions()
    return {
        "root": str(store.root),
        "count": len(sessions),
        "sessions": [s.to_summary() for s in sessions],
    }


def refresh(store: SessionStore) -> dict[str, Any]:
    """Re-scan the watched root. Use this after a new run was logged."""
    sessions = store.refresh()
    return {"refreshed": True, "count": len(sessions)}


def get_session(store: SessionStore, session_id: str) -> dict[str, Any]:
    sess = _require(store, session_id)
    data = store.load(session_id)
    result = store.score(session_id)
    return {
        "session": sess.to_summary(),
        "score": result.model_dump(),
        "meta": data.meta.model_dump(),
        "step_count": len(data.trace),
        "tool_call_count": len(data.tool_calls),
        "diff_count": len(data.diffs),
    }


def get_score(store: SessionStore, session_id: str) -> dict[str, Any]:
    _require(store, session_id)
    return store.score(session_id).model_dump()


def get_trace(store: SessionStore, session_id: str, limit: int | None = None) -> dict[str, Any]:
    _require(store, session_id)
    trace = store.load(session_id).trace
    items = trace if limit is None else trace[:limit]
    return {"session_id": session_id, "total": len(trace), "trace": [s.model_dump() for s in items]}


def get_tool_calls(
    store: SessionStore, session_id: str, only_failed: bool = False, limit: int | None = None
) -> dict[str, Any]:
    _require(store, session_id)
    calls = store.load(session_id).tool_calls
    if only_failed:
        calls = [c for c in calls if not c.success]
    items = calls if limit is None else calls[:limit]
    return {
        "session_id": session_id,
        "total": len(calls),
        "tool_calls": [c.model_dump() for c in items],
    }


def get_diffs(store: SessionStore, session_id: str, only_wasted: bool = False) -> dict[str, Any]:
    _require(store, session_id)
    diffs = store.load(session_id).diffs
    if only_wasted:
        diffs = [d for d in diffs if d.is_wasted]
    return {
        "session_id": session_id,
        "total": len(diffs),
        "diffs": [d.model_dump() for d in diffs],
    }


def get_dashboard_url(store: SessionStore, port: int) -> dict[str, Any]:
    """Tell Claude where the live dashboard is so it can point the user at it."""
    return {"url": f"http://127.0.0.1:{port}", "root": str(store.root)}


def _require(store: SessionStore, session_id: str) -> Any:
    sess = store.get(session_id)
    if sess is None:
        raise ValueError(
            f"Unknown session '{session_id}'. Call refresh() first, or check list_sessions()."
        )
    return sess
