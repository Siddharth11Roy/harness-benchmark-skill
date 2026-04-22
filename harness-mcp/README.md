# harness-mcp

Live dashboard + MCP server for [agent-harness](../README.md) benchmark logs.

The MCP server and the dashboard read through the **same** `SessionStore`, so
anything Claude fetches via tools is exactly what the user sees in the browser.

```
┌──────────────┐      ┌────────────────────┐      ┌─────────────────────┐
│ Claude Code  │◀───▶│  harness-mcp       │◀───▶│  agent_logs/*       │
│ (skill)      │ MCP  │  ├─ MCP stdio      │ FS   │   trace.md          │
│              │      │  └─ FastAPI (HTTP) │      │   tool_calls.json   │
└──────────────┘      └────────────────────┘      │   diff_summary.md   │
        ▲                       │                  │   session_meta.json │
        │                       ▼                  └─────────────────────┘
        │              http://127.0.0.1:3737
        └─── you open this in a browser
```

## Install

```bash
pip install -e ../  # the parent agent-harness package
pip install -e .
```

## Run

```bash
HARNESS_LOGS_ROOT=./examples harness-mcp
```

This:
1. Starts the dashboard on `http://127.0.0.1:3737` (or next free port).
2. Speaks MCP over stdio so Claude Code can connect.

## Wire it into Claude Code

One-liner (recommended — no JSON editing):

```cmd
claude mcp add harness --scope user --env HARNESS_LOGS_ROOT=D:/N Projects/Harness-Benchmark-Skill/examples -- harness-mcp
```

Verify:

```cmd
claude mcp list
```

You should see `harness` listed. Restart Claude Code.

Then install the skill so Claude knows when to use the tools:

```cmd
copy skills\harness-dashboard.md %USERPROFILE%\.claude\skills\
```

## Use

1. Start Claude Code in any project.
2. First tool call spins up the MCP server — open `http://127.0.0.1:3737`.
3. Badge at the bottom-right reads `harness MCP · connected`.
4. Prompt:
   > *Show me the latest harness session.*

## MCP tools

| Tool | Purpose |
|---|---|
| `list_sessions` | List all discovered sessions |
| `refresh` | Rescan the watched root (re-access control) |
| `get_session` | Summary + score for one session |
| `get_score` | Full score breakdown |
| `get_trace` | Step-by-step trace |
| `get_tool_calls` | Tool calls (filterable to failures) |
| `get_diffs` | Diffs (filterable to wasted) |
| `get_dashboard_url` | Browser URL |

## Tests

```bash
pip install -e ".[dev]"
pytest
```

21 tests cover the store, MCP tool dispatch, refresh flow, and dashboard HTTP.

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| `Port :3737 busy` / dashboard won't start | Server auto-falls-back to the next free OS-assigned port. Check the stderr line `[harness-mcp] dashboard: http://127.0.0.1:<port>` for the real URL, or set `$env:HARNESS_DASHBOARD_PORT="3838"` to pin it. |
| Stale Python process holding the port | `Get-Process python \| Stop-Process` (PowerShell) or `taskkill /F /IM python.exe` (cmd), then restart. |
| Badge stays `standalone` even though Claude is wired | The MCP server boots a *separate* dashboard on first tool call. Use Claude (e.g. *"list harness sessions"*) to trigger it, then refresh the browser tab. The standalone `harness-dashboard` you launched is a different process. |
| Badge says `offline` | The dashboard process died. Check the terminal for tracebacks; common cause is `agent_logs/` containing a malformed `tool_calls.json`. |
| Claude says "no harness tools" after `claude mcp add` | Restart Claude Code — MCP servers are loaded at startup. Verify with `claude mcp list` and `/mcp` inside a session. |
| `list_sessions` returns `[]` even though logs exist | Either the root is wrong (`get_dashboard_url` echoes the watched root) or the log dir is missing one of `trace.md`, `tool_calls.json`, `diff_summary.md` — all three are required for discovery. Call `refresh` after fixing. |
| `harness-mcp` / `harness-dashboard` not on PATH | You skipped `pip install -e ./harness-mcp`. Re-run from the project root. On Windows, also confirm Python's Scripts folder is on PATH (`python -m site --user-base`). |
| `ModuleNotFoundError: harness` | The parent `agent-harness` package isn't installed. Run `pip install -e .` from `Harness-Benchmark-Skill/` first, then `pip install -e ./harness-mcp`. |
