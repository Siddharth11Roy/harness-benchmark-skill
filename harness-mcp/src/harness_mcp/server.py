"""MCP stdio server. Spawns the dashboard HTTP server in a background thread
so opening the browser shows the SAME data Claude is reading via tools.
"""
from __future__ import annotations

import asyncio
import json
import os
import socket
import sys
import threading
from pathlib import Path
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

from . import tools
from .store import SessionStore


DEFAULT_PORT = 3737


def _free_port(preferred: int) -> int:
    """Try preferred, fall back to OS-assigned."""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.bind(("127.0.0.1", preferred))
        s.close()
        return preferred
    except OSError:
        s.close()
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as t:
            t.bind(("127.0.0.1", 0))
            return t.getsockname()[1]


def _start_dashboard(store: SessionStore, port: int) -> None:
    import uvicorn
    from .dashboard import create_app

    app = create_app(store, mcp_connected=True)
    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning")
    server = uvicorn.Server(config)

    def run():
        try:
            asyncio.run(server.serve())
        except Exception as e:
            sys.stderr.write(f"[harness-mcp] dashboard error: {e}\n")

    t = threading.Thread(target=run, daemon=True, name="harness-dashboard")
    t.start()


def build_server(store: SessionStore, port: int) -> Server:
    server = Server("harness-mcp")

    @server.list_tools()
    async def list_tools() -> list[Tool]:
        return [
            Tool(
                name="list_sessions",
                description="List all benchmark sessions discovered under the watched root.",
                inputSchema={"type": "object", "properties": {}, "additionalProperties": False},
            ),
            Tool(
                name="refresh",
                description=(
                    "Re-scan the watched root for new agent_logs/ sessions. "
                    "Call this after the user runs `/harness score` or adds a new run."
                ),
                inputSchema={"type": "object", "properties": {}, "additionalProperties": False},
            ),
            Tool(
                name="get_session",
                description="Get summary, score, and counts for one session.",
                inputSchema={
                    "type": "object",
                    "properties": {"session_id": {"type": "string"}},
                    "required": ["session_id"],
                    "additionalProperties": False,
                },
            ),
            Tool(
                name="get_score",
                description="Get the full harness score breakdown for one session.",
                inputSchema={
                    "type": "object",
                    "properties": {"session_id": {"type": "string"}},
                    "required": ["session_id"],
                    "additionalProperties": False,
                },
            ),
            Tool(
                name="get_trace",
                description="Get the step-by-step trace for one session. Use limit to cap.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "session_id": {"type": "string"},
                        "limit": {"type": "integer", "minimum": 1},
                    },
                    "required": ["session_id"],
                    "additionalProperties": False,
                },
            ),
            Tool(
                name="get_tool_calls",
                description="Get tool calls for one session. only_failed filters to failures.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "session_id": {"type": "string"},
                        "only_failed": {"type": "boolean", "default": False},
                        "limit": {"type": "integer", "minimum": 1},
                    },
                    "required": ["session_id"],
                    "additionalProperties": False,
                },
            ),
            Tool(
                name="get_diffs",
                description="Get diffs for one session. only_wasted filters to wasted work.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "session_id": {"type": "string"},
                        "only_wasted": {"type": "boolean", "default": False},
                    },
                    "required": ["session_id"],
                    "additionalProperties": False,
                },
            ),
            Tool(
                name="get_dashboard_url",
                description="Return the URL of the live dashboard the user can open in a browser.",
                inputSchema={"type": "object", "properties": {}, "additionalProperties": False},
            ),
        ]

    @server.call_tool()
    async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
        try:
            result = _dispatch(name, arguments, store, port)
            return [TextContent(type="text", text=json.dumps(result, indent=2, default=str))]
        except Exception as e:
            return [TextContent(type="text", text=f"ERROR: {e}")]

    return server


def _dispatch(name: str, args: dict[str, Any], store: SessionStore, port: int) -> dict:
    args = args or {}
    if name == "list_sessions":
        return tools.list_sessions(store)
    if name == "refresh":
        return tools.refresh(store)
    if name == "get_session":
        return tools.get_session(store, args["session_id"])
    if name == "get_score":
        return tools.get_score(store, args["session_id"])
    if name == "get_trace":
        return tools.get_trace(store, args["session_id"], args.get("limit"))
    if name == "get_tool_calls":
        return tools.get_tool_calls(
            store, args["session_id"], bool(args.get("only_failed", False)), args.get("limit")
        )
    if name == "get_diffs":
        return tools.get_diffs(store, args["session_id"], bool(args.get("only_wasted", False)))
    if name == "get_dashboard_url":
        return tools.get_dashboard_url(store, port)
    raise ValueError(f"Unknown tool: {name}")


async def _serve(store: SessionStore, port: int) -> None:
    server = build_server(store, port)
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


def main() -> None:
    root = Path(os.environ.get("HARNESS_LOGS_ROOT", "."))
    preferred = int(os.environ.get("HARNESS_DASHBOARD_PORT", str(DEFAULT_PORT)))
    port = _free_port(preferred)
    store = SessionStore(root=root)

    _start_dashboard(store, port)
    sys.stderr.write(f"[harness-mcp] dashboard: http://127.0.0.1:{port}\n")
    sys.stderr.write(f"[harness-mcp] watching: {store.root}\n")

    try:
        asyncio.run(_serve(store, port))
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
