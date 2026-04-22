from __future__ import annotations
import math
from .schemas import HarnessInput, HarnessResult, MetricBreakdown

WEIGHTS = {
    "completion": 0.30,
    "efficiency": 0.18,
    "tool_success": 0.15,
    "recovery": 0.15,
    "diff_quality": 0.12,
    "planning_quality": 0.10,
}

OVERHEAD_PHASES = {"MAINTAIN"}
FAILED_PHASES = {"FAILED"}
WRITE_TOOLS = {"write_file", "Write", "edit", "Edit", "NotebookEdit"}
READ_TOOLS = {"read_file", "Read", "read_many_files", "Glob", "Grep"}


def _sigmoid(x: float, k: float = 10.0, x0: float = 0.45) -> float:
    """Sigmoid with clamped argument to prevent math.exp overflow."""
    arg = max(-50.0, min(50.0, -k * (x - x0)))
    return 1.0 / (1.0 + math.exp(arg))


def _grade(score: float) -> str:
    if score >= 0.90:
        return "A"
    if score >= 0.80:
        return "B+"
    if score >= 0.70:
        return "B"
    if score >= 0.60:
        return "C"
    return "D"


def compute_completion(data: HarnessInput) -> tuple[float, str]:
    total = len(data.trace)
    if total == 0:
        return 0.0, "No steps recorded"
    failed = sum(1 for s in data.trace if s.phase == "FAILED")
    successful = total - failed
    return successful / total, f"{successful}/{total} steps successful"


def compute_efficiency(data: HarnessInput) -> tuple[float, str]:
    total_steps = len(data.trace)
    if total_steps == 0:
        return 0.0, "No steps recorded"
    productive_steps = sum(
        1 for s in data.trace if s.phase not in OVERHEAD_PHASES | FAILED_PHASES
    )
    failed_steps = sum(1 for s in data.trace if s.phase == "FAILED")
    completed = total_steps - failed_steps

    if productive_steps == 0:
        return 0.0, "No productive steps"

    raw = completed / productive_steps
    return min(_sigmoid(raw), 1.0), (
        f"{completed} completed / {productive_steps} productive (raw={raw:.3f})"
    )


def compute_tool_success(data: HarnessInput) -> tuple[float, str]:
    total = len(data.tool_calls)
    if total == 0:
        return 1.0, "No tool calls recorded"
    successful = sum(1 for t in data.tool_calls if t.success)
    return successful / total, f"{successful}/{total} calls succeeded"


def compute_recovery(data: HarnessInput) -> tuple[float, str]:
    """For each step that had at least one failure, did a later call succeed?

    'Later' means: a successful call later within the same step (by list order),
    OR any successful call in step+1. Uses enumerate — never .index() — so
    identical tool calls don't alias.
    """
    calls_by_step: dict[int, list[tuple[int, bool]]] = {}
    for pos, t in enumerate(data.tool_calls):
        calls_by_step.setdefault(t.step, []).append((pos, t.success))

    failure_steps = sorted(s for s, items in calls_by_step.items() if any(not ok for _, ok in items))
    if not failure_steps:
        return 1.0, "No failures to recover from"

    recovered = 0
    for step in failure_steps:
        items = calls_by_step[step]
        last_fail_pos = max(pos for pos, ok in items if not ok)
        later_success_same_step = any(pos > last_fail_pos and ok for pos, ok in items)
        next_step_any_success = any(ok for _, ok in calls_by_step.get(step + 1, []))
        if later_success_same_step or next_step_any_success:
            recovered += 1

    return recovered / len(failure_steps), f"{recovered}/{len(failure_steps)} failure events recovered"


def compute_diff_quality(data: HarnessInput) -> tuple[float, str]:
    total_added = sum(d.lines_added for d in data.diffs)
    total_removed = sum(d.lines_removed for d in data.diffs)
    total_changes = total_added + total_removed
    if total_changes == 0:
        return 1.0, "No diffs recorded"

    wasted_entries = [d for d in data.diffs if d.is_wasted]
    wasted_total = sum(d.lines_added + d.lines_removed for d in wasted_entries)

    pivot_discount = 0.5 if any(d.is_intentional_pivot for d in wasted_entries) else 1.0
    raw_noise = wasted_total / total_changes
    adjusted_noise = min(1.0, raw_noise * pivot_discount)
    score = max(0.0, 1.0 - adjusted_noise)

    return score, (
        f"{wasted_total}/{total_changes} wasted lines "
        f"(noise={raw_noise:.1%}, adjusted={adjusted_noise:.1%})"
    )


def compute_planning_quality(data: HarnessInput) -> tuple[float, str]:
    write_calls = sum(1 for t in data.tool_calls if t.tool in WRITE_TOOLS)
    read_calls = sum(1 for t in data.tool_calls if t.tool in READ_TOOLS)
    if write_calls == 0:
        return 1.0, "No write calls (nothing to plan for)"
    ratio = read_calls / write_calls
    return min(_sigmoid(ratio, k=8, x0=0.25), 1.0), (
        f"{read_calls} reads / {write_calls} writes (ratio={ratio:.2f})"
    )


def score(data: HarnessInput) -> HarnessResult:
    c, c_detail = compute_completion(data)
    e, e_detail = compute_efficiency(data)
    t, t_detail = compute_tool_success(data)
    r, r_detail = compute_recovery(data)
    d, d_detail = compute_diff_quality(data)
    p, p_detail = compute_planning_quality(data)

    composite = (
        WEIGHTS["completion"] * c
        + WEIGHTS["efficiency"] * e
        + WEIGHTS["tool_success"] * t
        + WEIGHTS["recovery"] * r
        + WEIGHTS["diff_quality"] * d
        + WEIGHTS["planning_quality"] * p
    )

    total_steps = len(data.trace)
    productive = sum(1 for s in data.trace if s.phase not in OVERHEAD_PHASES | FAILED_PHASES)
    total_calls = len(data.tool_calls)
    failed_calls = sum(1 for tc in data.tool_calls if not tc.success)
    lines_added = sum(df.lines_added for df in data.diffs)
    lines_removed = sum(df.lines_removed for df in data.diffs)
    wasted = sum(df.lines_added + df.lines_removed for df in data.diffs if df.is_wasted)
    neg_iv = sum(1 for iv in data.meta.user_interventions if iv.type == "negative")
    pos_iv = sum(1 for iv in data.meta.user_interventions if iv.type == "positive")

    return HarnessResult(
        project=data.meta.project,
        model=data.meta.model,
        date=data.meta.date,
        score=round(composite, 3),
        grade=_grade(composite),
        metrics=MetricBreakdown(
            completion=round(c, 3), efficiency=round(e, 3),
            tool_success=round(t, 3), recovery=round(r, 3),
            diff_quality=round(d, 3), planning_quality=round(p, 3),
            composite=round(composite, 3),
            completion_detail=c_detail, efficiency_detail=e_detail,
            tool_success_detail=t_detail, recovery_detail=r_detail,
            diff_quality_detail=d_detail, planning_quality_detail=p_detail,
        ),
        total_steps=total_steps,
        productive_steps=productive,
        total_tool_calls=total_calls,
        failed_tool_calls=failed_calls,
        lines_added=lines_added,
        lines_removed=lines_removed,
        wasted_lines=wasted,
        negative_interventions=neg_iv,
        positive_interventions=pos_iv,
    )
