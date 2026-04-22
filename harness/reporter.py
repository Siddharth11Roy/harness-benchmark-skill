from __future__ import annotations
from pathlib import Path
from .schemas import HarnessResult

BAR_WIDTH = 40


def _bar(value: float, width: int = BAR_WIDTH) -> str:
    filled = round(value * width)
    empty = width - filled
    return "█" * filled + "░" * empty


def _grade_desc(grade: str) -> str:
    return {
        "A":  "Excellent — minimal waste, perfect recovery",
        "B+": "Strong — minor inefficiencies, good recovery",
        "B":  "Good — some wandering, decent recovery",
        "C":  "Average — noticeable waste, partial recovery",
        "D":  "Weak — significant looping, poor recovery",
    }.get(grade, "")


def render(result: HarnessResult) -> str:
    m = result.metrics
    lines: list[str] = []

    lines += [
        "# Agent Harness Evaluation Report",
        "",
        f"**Project:** {result.project}",
        f"**Model:** {result.model}",
        f"**Date:** {result.date}",
        f"**Log Sources:** `trace.md` ({result.total_steps} steps) · "
        f"`tool_calls.json` ({result.total_tool_calls} calls) · "
        f"`diff_summary.md`",
        "",
        "---",
        "",
        "## Composite Harness Score",
        "",
        "```",
        "┌─────────────────────────────────────────────────────┐",
        f"│                                                     │",
        f"│         HARNESS SCORE:  {result.score:.3f} / 1.000             │",
        f"│                                                     │",
        f"│  {_bar(result.score)}  {result.score*100:.1f}%   │",
        f"│                                                     │",
        "└─────────────────────────────────────────────────────┘",
        "```",
        "",
        f"**Grade: {result.grade}** — {_grade_desc(result.grade)}",
        "",
        "### Formula",
        "",
        "```",
        "harness_score = 0.30 × completion",
        "             + 0.18 × efficiency",
        "             + 0.15 × tool_success",
        "             + 0.15 × recovery",
        "             + 0.12 × diff_quality",
        "             + 0.10 × planning_quality",
        "```",
        "",
        "### Score Breakdown",
        "",
        "| Metric | Weight | Raw | Weighted | Detail |",
        "|---|---|---|---|---|",
        f"| Completion | 0.30 | {m.completion:.3f} | {0.30*m.completion:.3f} | {m.completion_detail} |",
        f"| Efficiency | 0.18 | {m.efficiency:.3f} | {0.18*m.efficiency:.3f} | {m.efficiency_detail} |",
        f"| Tool Success | 0.15 | {m.tool_success:.3f} | {0.15*m.tool_success:.3f} | {m.tool_success_detail} |",
        f"| Recovery | 0.15 | {m.recovery:.3f} | {0.15*m.recovery:.3f} | {m.recovery_detail} |",
        f"| Diff Quality | 0.12 | {m.diff_quality:.3f} | {0.12*m.diff_quality:.3f} | {m.diff_quality_detail} |",
        f"| Planning Quality | 0.10 | {m.planning_quality:.3f} | {0.10*m.planning_quality:.3f} | {m.planning_quality_detail} |",
        f"| **TOTAL** | **1.00** | | **{m.composite:.3f}** | |",
        "",
        "---",
        "",
        "## Metric Bars",
        "",
        "```",
        f"Completion       {_bar(m.completion, 30)}  {m.completion*100:.1f}%",
        f"Efficiency       {_bar(m.efficiency, 30)}  {m.efficiency*100:.1f}%",
        f"Tool Success     {_bar(m.tool_success, 30)}  {m.tool_success*100:.1f}%",
        f"Recovery         {_bar(m.recovery, 30)}  {m.recovery*100:.1f}%",
        f"Diff Quality     {_bar(m.diff_quality, 30)}  {m.diff_quality*100:.1f}%",
        f"Planning Quality {_bar(m.planning_quality, 30)}  {m.planning_quality*100:.1f}%",
        "```",
        "",
        "---",
        "",
        "## Session Summary",
        "",
        "| Stat | Value |",
        "|---|---|",
        f"| Total steps | {result.total_steps} |",
        f"| Productive steps | {result.productive_steps} |",
        f"| Total tool calls | {result.total_tool_calls} |",
        f"| Failed tool calls | {result.failed_tool_calls} |",
        f"| Lines added | {result.lines_added:,} |",
        f"| Lines removed | {result.lines_removed:,} |",
        f"| Wasted lines | {result.wasted_lines:,} |",
        f"| Negative interventions | {result.negative_interventions} |",
        f"| Positive interventions | {result.positive_interventions} |",
        "",
        "---",
        "",
        "## User Interventions",
        "",
    ]

    if result.negative_interventions + result.positive_interventions == 0:
        lines.append("No user interventions recorded.")
    else:
        neg = result.negative_interventions
        pos = result.positive_interventions
        total_iv = neg + pos
        lines += [
            f"- **Negative (redirects/corrections):** {neg}/{total_iv}",
            f"- **Positive (new scope/approvals):** {pos}/{total_iv}",
            "",
            "> Each negative intervention is a signal the agent went off-track.",
            "> High negative count lowers the effective completion and efficiency scores.",
        ]

    lines += [
        "",
        "---",
        "",
        "## Grade Reference",
        "",
        "| Range | Grade | Description |",
        "|---|---|---|",
        "| 0.90 – 1.00 | A | Excellent — minimal waste, perfect recovery |",
        "| 0.80 – 0.89 | B+ | Strong — minor inefficiencies, good recovery |",
        "| 0.70 – 0.79 | B | Good — some wandering, decent recovery |",
        "| 0.60 – 0.69 | C | Average — noticeable waste, partial recovery |",
        "| 0.00 – 0.59 | D | Weak — significant looping, poor recovery |",
        "",
        "---",
        "",
        "*Generated by agent-harness v0.1.0*",
    ]

    return "\n".join(lines)


def write_report(result: HarnessResult, output_path: Path) -> None:
    output_path.write_text(render(result), encoding="utf-8")
