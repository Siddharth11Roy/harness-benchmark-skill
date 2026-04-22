---
name: harness-dashboard
description: Inspect agent-harness benchmark sessions through the live dashboard MCP. Use when the user asks about a benchmark run, score, trace, tool calls, or wasted diffs — or wants to see results in a browser.
---

# /harness-dashboard

You have access to a live dashboard MCP server (`harness-mcp`) that watches a
directory of `agent_logs/` and exposes both:

- A **browser dashboard** at `http://127.0.0.1:<port>` (the user opens this)
- **MCP tools** that return the same data as JSON (you call these)

## When to use this skill

- The user asks about scores, grades, trace, tool calls, or diffs from a run.
- The user just produced new logs (`/harness score`) and wants you to interpret them.
- The user references "the dashboard", "the latest run", or a session by name.

## Tools available

| Tool | Use it for |
|---|---|
| `list_sessions` | What sessions are there? Always start here if you don't know the id. |
| `get_session` | Summary + score + counts for one session. |
| `get_score` | Just the metric breakdown. |
| `get_trace` | Step-by-step trace (use `limit` to keep it short). |
| `get_tool_calls` | Tool calls. Pass `only_failed: true` to focus on errors. |
| `get_diffs` | Diffs. Pass `only_wasted: true` to focus on thrown-away code. |
| `refresh` | Re-scan the watched root. Call this if `list_sessions` looks stale or after the user runs `/harness score`. |
| `get_dashboard_url` | Get the URL to point the user at the browser view. |

## Required behavior

1. **Always start with `list_sessions`** when you don't know the session id —
   never guess.
2. **Refresh before reporting "not found"**. If the user references a session
   you don't see, call `refresh` once and re-check before saying it doesn't exist.
3. **Don't dump full payloads**. Use `limit`, `only_failed`, `only_wasted` to
   keep responses focused. Summarize for the user; cite specific step numbers.
4. **Point at the dashboard for visuals**. When the user wants to *see* the
   data, call `get_dashboard_url` and share the link rather than pasting tables.
5. **Never recompute scores yourself** — `get_score` is authoritative.
