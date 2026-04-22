"""PostToolUse hook for Claude Code.

Captures real tool calls verbatim into agent_logs/tool_calls.json — solves the
self-reporting bias where the agent narrates its own performance.

Install via .claude/settings.json:

    {
      "hooks": {
        "PostToolUse": [{
          "matcher": "Write|Edit|Read|Bash|Glob|Grep|NotebookEdit",
          "hooks": [{
            "type": "command",
            "command": "python -m harness.hook_capture"
          }]
        }]
      }
    }

Reads JSON payload from stdin, appends one entry to agent_logs/tool_calls.json.
Silently no-ops if agent_logs/ doesn't exist (so it doesn't pollute random projects).
Step numbers are left as 0 — the /harness log skill assigns them retroactively.
"""
from __future__ import annotations
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

LOG_DIR = Path("agent_logs")
TOOL_CALLS_FILE = LOG_DIR / "tool_calls.json"
MAX_INPUT_CHARS = 500
MAX_OUTPUT_CHARS = 500


def _summarize_input(tool_name: str, tool_input: dict) -> str:
    if not isinstance(tool_input, dict):
        return str(tool_input)[:MAX_INPUT_CHARS]
    # Prefer the most distinguishing field per common tool
    for key in ("file_path", "command", "pattern", "path", "url"):
        if key in tool_input and tool_input[key]:
            return str(tool_input[key])[:MAX_INPUT_CHARS]
    return json.dumps(tool_input, default=str)[:MAX_INPUT_CHARS]


def _summarize_output(tool_response) -> tuple[str, bool]:
    success = True
    if isinstance(tool_response, dict):
        if tool_response.get("error") or tool_response.get("isError"):
            success = False
        for key in ("output", "content", "result", "stdout", "filePath"):
            if key in tool_response and tool_response[key]:
                return str(tool_response[key])[:MAX_OUTPUT_CHARS], success
        return json.dumps(tool_response, default=str)[:MAX_OUTPUT_CHARS], success
    return str(tool_response)[:MAX_OUTPUT_CHARS], success


def main() -> int:
    if not LOG_DIR.exists():
        return 0  # opt-in: only log when user has /harness init'd

    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0  # never break the agent on bad input

    tool_name = payload.get("tool_name", "unknown")
    tool_input = payload.get("tool_input", {}) or {}
    tool_response = payload.get("tool_response", {}) or {}

    output_summary, success = _summarize_output(tool_response)
    entry = {
        "step": 0,  # assigned later by /harness log
        "tool": tool_name,
        "input": _summarize_input(tool_name, tool_input),
        "output_summary": output_summary,
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "success": success,
    }

    try:
        existing = json.loads(TOOL_CALLS_FILE.read_text(encoding="utf-8"))
        if isinstance(existing, dict):
            calls = existing.get("calls", [])
            calls.append(entry)
            existing["calls"] = calls
            TOOL_CALLS_FILE.write_text(json.dumps(existing, indent=2), encoding="utf-8")
        else:
            existing.append(entry)
            TOOL_CALLS_FILE.write_text(json.dumps(existing, indent=2), encoding="utf-8")
    except Exception:
        # If the file is corrupt or missing, start fresh — never crash the hook
        TOOL_CALLS_FILE.write_text(json.dumps([entry], indent=2), encoding="utf-8")

    return 0


if __name__ == "__main__":
    sys.exit(main())
