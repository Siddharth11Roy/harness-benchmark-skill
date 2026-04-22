"""FastAPI dashboard exposing the same data the MCP server returns.

The dashboard and MCP server read through the SAME SessionStore, so anything
the user sees in the browser is exactly what Claude can fetch via MCP tools.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .store import SessionStore


STATIC_DIR = Path(__file__).parent / "static"


def create_app(store: SessionStore, mcp_connected: bool = False) -> FastAPI:
    app = FastAPI(title="harness-mcp dashboard", version="0.1.0")

    @app.get("/api/status")
    def api_status():
        return {"mcp_connected": mcp_connected, "root": str(store.root)}

    @app.get("/api/sessions")
    def api_sessions():
        return {"root": str(store.root), "sessions": [s.to_summary() for s in store.list_sessions()]}

    @app.post("/api/refresh")
    def api_refresh():
        sessions = store.refresh()
        return {"refreshed": True, "count": len(sessions)}

    @app.get("/api/sessions/{session_id}")
    def api_session(session_id: str):
        sess = store.get(session_id)
        if sess is None:
            raise HTTPException(404, f"Unknown session: {session_id}")
        try:
            data = store.load(session_id)
            result = store.score(session_id)
        except Exception as exc:
            raise HTTPException(500, f"Failed to load: {exc}") from exc
        return {
            "session": sess.to_summary(),
            "score": result.model_dump(),
            "trace": [s.model_dump() for s in data.trace],
            "tool_calls": [t.model_dump() for t in data.tool_calls],
            "diffs": [d.model_dump() for d in data.diffs],
            "meta": data.meta.model_dump(),
        }

    @app.get("/api/sessions/{session_id}/score")
    def api_score(session_id: str):
        try:
            return JSONResponse(store.score(session_id).model_dump())
        except KeyError as e:
            raise HTTPException(404, str(e))

    @app.get("/")
    def index():
        return FileResponse(STATIC_DIR / "index.html")

    if STATIC_DIR.exists():
        app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    return app


def run() -> None:
    import uvicorn
    root = Path(os.environ.get("HARNESS_LOGS_ROOT", "."))
    port = int(os.environ.get("HARNESS_DASHBOARD_PORT", "3737"))
    store = SessionStore(root=root)
    app = create_app(store)
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")


if __name__ == "__main__":
    run()
