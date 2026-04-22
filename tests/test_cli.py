from __future__ import annotations
import json
from pathlib import Path
from click.testing import CliRunner

from harness.cli import main


def test_cli_init_creates_files(tmp_path: Path):
    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path):
        result = runner.invoke(main, ["init", "logs"])
        assert result.exit_code == 0
        p = Path("logs")
        assert (p / "trace.md").exists()
        assert (p / "tool_calls.json").exists()
        assert (p / "diff_summary.md").exists()
        assert (p / "session_meta.json").exists()
        meta = json.loads((p / "session_meta.json").read_text())
        assert meta["harness_version"] == "1.0"


def test_cli_score_end_to_end(tmp_path: Path):
    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path):
        runner.invoke(main, ["init", "logs"])
        # Fill minimal data
        Path("logs/trace.md").write_text(
            "---\nSTEP: 1\nGOAL:\nWork\nRESULT:\nOK\n---\n", encoding="utf-8"
        )
        Path("logs/tool_calls.json").write_text(
            json.dumps([
                {"step": 1, "tool": "Read", "output_summary": "ok"},
                {"step": 1, "tool": "Write", "output_summary": "ok"},
            ]),
            encoding="utf-8",
        )
        Path("logs/diff_summary.md").write_text(
            "---\nSTEP: 1\nFILES CHANGED: a.py\nLINES ADDED: 5\nLINES REMOVED: 0\nREASON FOR CHANGE: add\n---\n",
            encoding="utf-8",
        )

        result = runner.invoke(main, ["score", "logs", "--json-out"])
        assert result.exit_code == 0, result.output
        assert Path("logs/harness_score.md").exists()
        assert Path("logs/harness_score.json").exists()
        data = json.loads(Path("logs/harness_score.json").read_text())
        assert 0 <= data["score"] <= 1


def test_cli_score_fail_below_threshold(tmp_path: Path):
    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path):
        runner.invoke(main, ["init", "logs"])
        # Mostly-failed session
        Path("logs/trace.md").write_text(
            "---\nSTEP: 1\nGOAL:\nAttempt\nRESULT:\ncancelled by user\n---\n",
            encoding="utf-8",
        )
        Path("logs/tool_calls.json").write_text(
            json.dumps([{"step": 1, "tool": "Bash", "output_summary": "error"}]),
            encoding="utf-8",
        )
        Path("logs/diff_summary.md").write_text(
            "---\nSTEP: 1\nFILES CHANGED: a.py\nLINES ADDED: 0\nLINES REMOVED: 0\nREASON FOR CHANGE: fail\n---\n",
            encoding="utf-8",
        )
        result = runner.invoke(main, ["score", "logs", "--fail-below", "0.95"])
        assert result.exit_code == 1


def test_cli_score_missing_dir(tmp_path: Path):
    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path):
        result = runner.invoke(main, ["score", "does_not_exist"])
        assert result.exit_code == 1
        assert "not found" in result.output.lower() or "not found" in (result.stderr or "").lower()
