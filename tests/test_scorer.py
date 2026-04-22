from __future__ import annotations
from harness.schemas import (
    HarnessInput, TraceStep, ToolCall, DiffEntry, SessionMeta,
)
from harness.scorer import (
    score, compute_completion, compute_efficiency,
    compute_tool_success, compute_recovery, compute_diff_quality,
    compute_planning_quality, _sigmoid, _grade,
)


def make_input(trace=None, calls=None, diffs=None, meta=None):
    return HarnessInput(
        trace=trace or [],
        tool_calls=calls or [],
        diffs=diffs or [],
        meta=meta or SessionMeta(),
    )


# ---------- Completion ----------
def test_completion_empty():
    assert compute_completion(make_input())[0] == 0.0


def test_completion_all_success():
    trace = [TraceStep(step=i, phase="BUILD") for i in range(1, 4)]
    score_val, _ = compute_completion(make_input(trace=trace))
    assert score_val == 1.0


def test_completion_with_failure():
    trace = [
        TraceStep(step=1, phase="BUILD"),
        TraceStep(step=2, phase="FAILED"),
        TraceStep(step=3, phase="BUILD"),
        TraceStep(step=4, phase="BUILD"),
    ]
    val, _ = compute_completion(make_input(trace=trace))
    assert val == 0.75


# ---------- Efficiency ----------
def test_efficiency_empty():
    assert compute_efficiency(make_input())[0] == 0.0


def test_efficiency_all_productive():
    trace = [TraceStep(step=i, phase="BUILD") for i in range(1, 5)]
    val, _ = compute_efficiency(make_input(trace=trace))
    assert val > 0.9  # sigmoid(1.0) ≈ 0.996


def test_efficiency_excludes_overhead():
    trace = [
        TraceStep(step=1, phase="BUILD"),
        TraceStep(step=2, phase="MAINTAIN"),  # overhead
        TraceStep(step=3, phase="BUILD"),
    ]
    # productive = 2 (steps 1,3), completed = 3 (none failed)
    # raw = 3/2 = 1.5 → sigmoid ≈ 1.0
    val, detail = compute_efficiency(make_input(trace=trace))
    assert val > 0.9
    assert "2 productive" in detail


# ---------- Tool Success ----------
def test_tool_success_no_calls():
    assert compute_tool_success(make_input())[0] == 1.0


def test_tool_success_partial():
    calls = [
        ToolCall(step=1, tool="Bash", input="", output_summary="", success=True),
        ToolCall(step=1, tool="Bash", input="", output_summary="", success=False),
        ToolCall(step=1, tool="Bash", input="", output_summary="", success=True),
    ]
    val, _ = compute_tool_success(make_input(calls=calls))
    assert abs(val - 2/3) < 1e-6


# ---------- Recovery ----------
def test_recovery_no_failures():
    calls = [ToolCall(step=1, tool="Read", input="", output_summary="", success=True)]
    assert compute_recovery(make_input(calls=calls))[0] == 1.0


def test_recovery_same_step():
    """Fail then succeed in the same step — counts as recovered."""
    calls = [
        ToolCall(step=1, tool="Bash", input="", output_summary="error", success=False),
        ToolCall(step=1, tool="Bash", input="", output_summary="ok", success=True),
    ]
    assert compute_recovery(make_input(calls=calls))[0] == 1.0


def test_recovery_next_step():
    """Fail in step 1, succeed in step 2 — counts as recovered."""
    calls = [
        ToolCall(step=1, tool="Bash", input="", output_summary="error", success=False),
        ToolCall(step=2, tool="Bash", input="", output_summary="ok", success=True),
    ]
    assert compute_recovery(make_input(calls=calls))[0] == 1.0


def test_recovery_not_recovered():
    """Failure with no later success anywhere — zero recovery."""
    calls = [
        ToolCall(step=1, tool="Bash", input="", output_summary="error", success=False),
    ]
    assert compute_recovery(make_input(calls=calls))[0] == 0.0


def test_recovery_identical_calls_do_not_alias():
    """Regression test for the old .index() bug: identical tool calls must not
    collapse to the same position."""
    calls = [
        ToolCall(step=1, tool="Bash", input="same", output_summary="error", success=False),
        ToolCall(step=1, tool="Bash", input="same", output_summary="error", success=False),
        ToolCall(step=1, tool="Bash", input="same", output_summary="ok", success=True),
    ]
    # Last fail is at position 1; success at position 2 comes after → recovered
    assert compute_recovery(make_input(calls=calls))[0] == 1.0


# ---------- Diff Quality ----------
def test_diff_quality_empty():
    assert compute_diff_quality(make_input())[0] == 1.0


def test_diff_quality_no_waste():
    diffs = [DiffEntry(step=1, lines_added=100, lines_removed=0)]
    assert compute_diff_quality(make_input(diffs=diffs))[0] == 1.0


def test_diff_quality_wasted_no_pivot():
    diffs = [
        DiffEntry(step=1, lines_added=100, lines_removed=0, is_wasted=True),
        DiffEntry(step=2, lines_added=100, lines_removed=0, is_wasted=False),
    ]
    # 100/200 = 50% noise, no pivot → score 0.5
    val, _ = compute_diff_quality(make_input(diffs=diffs))
    assert abs(val - 0.5) < 1e-6


def test_diff_quality_intentional_pivot_discount():
    diffs = [
        DiffEntry(step=1, lines_added=100, lines_removed=0, is_wasted=True,
                  is_intentional_pivot=True),
        DiffEntry(step=2, lines_added=100, lines_removed=0),
    ]
    # 50% noise * 0.5 discount = 25% adjusted → score 0.75
    val, _ = compute_diff_quality(make_input(diffs=diffs))
    assert abs(val - 0.75) < 1e-6


# ---------- Planning Quality ----------
def test_planning_no_writes():
    assert compute_planning_quality(make_input())[0] == 1.0


def test_planning_zero_reads():
    calls = [ToolCall(step=1, tool="Write", input="", output_summary="", success=True)]
    val, _ = compute_planning_quality(make_input(calls=calls))
    assert val < 0.5  # sigmoid(0) with k=8, x0=0.25 is low


def test_planning_balanced():
    calls = [
        ToolCall(step=1, tool="Read", input="", output_summary="", success=True),
        ToolCall(step=1, tool="Write", input="", output_summary="", success=True),
    ]
    val, _ = compute_planning_quality(make_input(calls=calls))
    assert val > 0.9  # ratio 1.0 → sigmoid high


# ---------- Sigmoid numeric stability ----------
def test_sigmoid_extreme_values():
    assert 0.0 <= _sigmoid(-1e6) <= 1.0
    assert 0.0 <= _sigmoid(1e6) <= 1.0


# ---------- Grade boundaries ----------
def test_grade_boundaries():
    assert _grade(0.95) == "A"
    assert _grade(0.85) == "B+"
    assert _grade(0.75) == "B"
    assert _grade(0.65) == "C"
    assert _grade(0.50) == "D"


# ---------- Integration ----------
def test_score_composite_weighted_correctly():
    """All metrics = 1.0 → composite should be 1.0."""
    trace = [TraceStep(step=i, phase="BUILD") for i in range(1, 5)]
    calls = [
        ToolCall(step=i, tool="Read", input="", output_summary="", success=True)
        for i in range(1, 5)
    ] + [
        ToolCall(step=i, tool="Write", input="", output_summary="", success=True)
        for i in range(1, 5)
    ]
    result = score(make_input(trace=trace, calls=calls))
    assert result.score >= 0.99  # allow tiny floating point slack
    assert result.grade == "A"
