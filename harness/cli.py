from __future__ import annotations
import json
import sys
from pathlib import Path

import click
from . import __version__
from .constants import SCHEMA_VERSION
from .parser import load_logs
from .scorer import score
from .reporter import render


@click.group()
@click.version_option(__version__, "--version", "-V")
def main():
    """agent-harness: benchmark AI agent sessions from structured logs."""


@main.command()
@click.argument("logs_dir", default="agent_logs", type=click.Path(exists=False))
@click.option("--output", "-o", default=None, help="Output path for harness_score.md")
@click.option("--json-out", is_flag=True, help="Also write harness_score.json")
@click.option("--fail-below", default=None, type=float, help="Exit code 1 if score < threshold")
def score_cmd(logs_dir, output, json_out, fail_below):
    """Compute harness score from LOGS_DIR (default: ./agent_logs)."""
    d = Path(logs_dir)
    if not d.exists():
        click.echo(f"Error: directory '{logs_dir}' not found.", err=True)
        sys.exit(1)

    required = ["trace.md", "tool_calls.json", "diff_summary.md"]
    missing = [f for f in required if not (d / f).exists()]
    if missing:
        click.echo(f"Error: missing required files: {', '.join(missing)}", err=True)
        sys.exit(1)

    try:
        data = load_logs(d)
    except Exception as exc:
        click.echo(f"Error reading logs: {exc}", err=True)
        sys.exit(1)
    result = score(data)
    report_md = render(result)

    out_path = Path(output) if output else d / "harness_score.md"
    out_path.write_text(report_md, encoding="utf-8")
    click.echo(f"Report written: {out_path}")

    if json_out:
        json_path = out_path.with_suffix(".json")
        json_path.write_text(result.model_dump_json(indent=2), encoding="utf-8")
        click.echo(f"JSON written:  {json_path}")

    click.echo(f"\nHARNESS SCORE: {result.score:.3f}  [{result.grade}]")

    if fail_below is not None and result.score < fail_below:
        click.echo(f"Score {result.score:.3f} is below threshold {fail_below:.3f} — failing.", err=True)
        sys.exit(1)


@main.command()
@click.argument("directory", default="agent_logs", type=click.Path())
def init(directory):
    """Scaffold an agent_logs/ directory with empty template files."""
    d = Path(directory)
    d.mkdir(parents=True, exist_ok=True)

    trace = d / "trace.md"
    if not trace.exists():
        trace.write_text(
            "# Agent Trace Log\n\n"
            "---\n\n"
            "STEP: 1\n\n"
            "GOAL:\n\n"
            "FILES READ:\n\n"
            "FILES MODIFIED:\n\n"
            "TOOLS USED:\n\n"
            "DECISION:\n\n"
            "RESULT:\n\n"
            "NEXT PLAN:\n\n"
            "---\n",
            encoding="utf-8",
        )

    calls = d / "tool_calls.json"
    if not calls.exists():
        calls.write_text("[\n]\n", encoding="utf-8")

    diff = d / "diff_summary.md"
    if not diff.exists():
        diff.write_text(
            "# Diff Summary Log\n\n"
            "---\n\n"
            "STEP: 1\n"
            "FILES CHANGED:\n"
            "LINES ADDED: 0\n"
            "LINES REMOVED: 0\n"
            "REASON FOR CHANGE:\n\n"
            "---\n",
            encoding="utf-8",
        )

    meta = d / "session_meta.json"
    if not meta.exists():
        meta.write_text(
            json.dumps({
                "harness_version": SCHEMA_VERSION,
                "model": "unknown",
                "project": "unknown",
                "date": "",
                "total_time_minutes": None,
                "build_success": True,
                "test_pass_rate": None,
                "task_prompt": "",
                "user_interventions": []
            }, indent=2),
            encoding="utf-8",
        )

    click.echo(f"Initialized harness logs at: {d.resolve()}")
    click.echo("  trace.md, tool_calls.json, diff_summary.md, session_meta.json")


# Alias: `harness score` maps to `score` command
main.add_command(score_cmd, name="score")


if __name__ == "__main__":
    main()
