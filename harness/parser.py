from __future__ import annotations
import json
import re
from pathlib import Path

from .constants import (
    MAX_FILE_BYTES, MAX_FIELD_CHARS, check_version,
    HarnessSizeError,
)
from .schemas import (
    TraceStep, ToolCall, DiffEntry, SessionMeta,
    UserIntervention, HarnessInput,
)

FIELD_LINE = re.compile(r"^([A-Z][A-Z ]*[A-Z]):\s*(.*)$")
FILE_ANNOTATION = re.compile(r"\s*\([^)]*\)")  # strips "(NEW)", "(DELETED)", etc.
FAILURE_KEYWORDS = ("error", "failed", "exception", "cancelled", "traceback")


def _read_capped(path: Path) -> str:
    """Read file but reject anything over MAX_FILE_BYTES."""
    if not path.exists():
        raise FileNotFoundError(str(path))
    size = path.stat().st_size
    if size > MAX_FILE_BYTES:
        raise HarnessSizeError(
            f"{path.name} is {size:,} bytes, exceeds limit {MAX_FILE_BYTES:,}. "
            f"Truncate or split the log."
        )
    return path.read_text(encoding="utf-8")


def _clip(s: str, limit: int = MAX_FIELD_CHARS) -> str:
    return s if len(s) <= limit else s[:limit] + "...[truncated]"


def _clean_filename(raw: str) -> str:
    return FILE_ANNOTATION.sub("", raw).strip()


def _has_marker(file_marker: str, marker: str) -> bool:
    return marker.upper() in file_marker.upper()


def _parse_block_fields(block: str) -> dict[str, str]:
    """Linear single-pass field parser. No backtracking, no ReDoS risk."""
    fields: dict[str, str] = {}
    current_field: str | None = None
    current_lines: list[str] = []

    for line in block.splitlines():
        m = FIELD_LINE.match(line)
        if m:
            if current_field is not None:
                fields[current_field] = _clip("\n".join(current_lines).strip())
            current_field = m.group(1).strip()
            tail = m.group(2)
            current_lines = [tail] if tail else []
        elif current_field is not None:
            current_lines.append(line)

    if current_field is not None:
        fields[current_field] = _clip("\n".join(current_lines).strip())
    return fields


def _bullet_list(text: str) -> list[str]:
    items = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.lower() == "none":
            continue
        items.append(line.lstrip("-* ").strip())
    return items


def _classify_phase(goal: str, result: str) -> str:
    g, r = goal.lower(), result.lower()
    if any(k in r for k in ("abandoned", "cancelled by user", "failed")):
        return "FAILED"
    if any(k in g for k in ("fix", "debug", "import error")):
        return "DEBUG"
    if any(k in g for k in ("verify", "test", "demo", "run full")):
        return "VERIFY"
    if any(k in g for k in ("plan", "pivot", "architecture")):
        return "PLAN"
    if any(k in g for k in ("log", "finalize", "readme", "document", "update agent")):
        return "MAINTAIN"
    if any(k in g for k in ("scaffold", "set up project", "structure", "install")):
        return "SCAFFOLD"
    return "BUILD"


def parse_tool_calls(path: Path) -> list[ToolCall]:
    raw = _read_capped(path)
    data = json.loads(raw)

    # Accept both legacy (bare list) and v1.0+ ({"version": ..., "calls": [...]})
    if isinstance(data, dict):
        check_version(data.get("harness_version", ""))
        items = data.get("calls", [])
    else:
        items = data

    if not isinstance(items, list):
        raise ValueError("tool_calls.json must be a JSON array or object with 'calls' key")

    calls: list[ToolCall] = []
    for entry in items:
        summary = str(entry.get("output_summary", "")).lower()
        explicit = entry.get("success")
        if explicit is not None:
            success = bool(explicit)
        else:
            success = not any(k in summary for k in FAILURE_KEYWORDS)
        calls.append(ToolCall(
            step=int(entry.get("step", 0)),
            tool=str(entry.get("tool", "unknown")),
            input=_clip(str(entry.get("input", ""))),
            output_summary=_clip(str(entry.get("output_summary", ""))),
            timestamp=entry.get("timestamp"),
            success=success,
        ))
    return calls


def parse_diff_summary(path: Path) -> list[DiffEntry]:
    text = _read_capped(path)
    entries: list[DiffEntry] = []

    for block in text.split("\n---"):
        if "STEP:" not in block:
            continue
        fields = _parse_block_fields(block)
        try:
            step = int(re.sub(r"[^\d]", "", fields.get("STEP", "0")) or 0)
        except ValueError:
            continue

        files_raw = [f.strip() for f in fields.get("FILES CHANGED", "").split(",") if f.strip()]
        try:
            lines_added = int(fields.get("LINES ADDED", "0") or 0)
        except ValueError:
            lines_added = 0
        try:
            lines_removed = int(fields.get("LINES REMOVED", "0") or 0)
        except ValueError:
            lines_removed = 0

        entries.append(DiffEntry(
            step=step,
            files_changed=files_raw,
            lines_added=lines_added,
            lines_removed=lines_removed,
            reason=fields.get("REASON FOR CHANGE", ""),
            is_wasted=False,           # filled in by detect_wasted()
            is_intentional_pivot=False,
        ))

    detect_wasted(entries)
    return entries


def detect_wasted(entries: list[DiffEntry]) -> None:
    """Mark diffs as wasted using STRUCTURAL signals only.

    A file is wasted if it appears with a (DELETED) marker anywhere in the session.
    Any diff that touches a wasted file is marked as wasted work.
    A wasted diff is marked as an intentional_pivot only if the user-provided
    reason text contains explicit pivot language.
    """
    deleted_files: set[str] = set()
    for d in entries:
        for f_marker in d.files_changed:
            if _has_marker(f_marker, "DELETED"):
                deleted_files.add(_clean_filename(f_marker))

    if not deleted_files:
        return

    pivot_phrases = ("pivot", "abandoned", "rebuilt with", "deliberate")
    for d in entries:
        touches_wasted = any(
            _clean_filename(f) in deleted_files for f in d.files_changed
        )
        if touches_wasted:
            d.is_wasted = True
            if any(p in d.reason.lower() for p in pivot_phrases):
                d.is_intentional_pivot = True


def parse_trace(path: Path) -> list[TraceStep]:
    text = _read_capped(path)
    steps: list[TraceStep] = []

    for block in text.split("\n---"):
        if "STEP:" not in block:
            continue
        fields = _parse_block_fields(block)
        try:
            step_num = int(re.sub(r"[^\d]", "", fields.get("STEP", "0")) or 0)
        except ValueError:
            continue

        goal = fields.get("GOAL", "")
        result = fields.get("RESULT", "")

        steps.append(TraceStep(
            step=step_num,
            goal=goal,
            files_read=_bullet_list(fields.get("FILES READ", "")),
            files_modified=_bullet_list(fields.get("FILES MODIFIED", "")),
            tools_used=_bullet_list(fields.get("TOOLS USED", "")),
            decision=fields.get("DECISION", ""),
            result=result,
            next_plan=fields.get("NEXT PLAN", ""),
            phase=_classify_phase(goal, result),
        ))
    return steps


def parse_session_meta(path: Path) -> SessionMeta:
    if not path.exists():
        return SessionMeta()
    raw = _read_capped(path)
    data = json.loads(raw)

    check_version(data.get("harness_version", ""))

    interventions = []
    for iv in data.get("user_interventions", []):
        iv_type = iv.get("type", "negative")
        if iv_type not in ("positive", "negative"):
            iv_type = "negative"
        interventions.append(UserIntervention(
            step=int(iv.get("step", 0)),
            prompt=_clip(str(iv.get("prompt", ""))),
            type=iv_type,
            reason=_clip(str(iv.get("reason", ""))),
        ))

    return SessionMeta(
        harness_version=data.get("harness_version", "1.0"),
        model=data.get("model", "unknown"),
        project=data.get("project", "unknown"),
        date=data.get("date", ""),
        total_time_minutes=data.get("total_time_minutes"),
        build_success=bool(data.get("build_success", True)),
        test_pass_rate=data.get("test_pass_rate"),
        task_prompt=_clip(str(data.get("task_prompt", ""))),
        user_interventions=interventions,
    )


def load_logs(directory: str | Path) -> HarnessInput:
    d = Path(directory)
    return HarnessInput(
        trace=parse_trace(d / "trace.md"),
        tool_calls=parse_tool_calls(d / "tool_calls.json"),
        diffs=parse_diff_summary(d / "diff_summary.md"),
        meta=parse_session_meta(d / "session_meta.json"),
    )
