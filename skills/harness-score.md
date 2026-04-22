# /harness score

Compute the harness benchmark score from `agent_logs/` and write `harness_score.md`.

## What this does

Delegates scoring to the `harness` CLI — the single source of truth for the formula.
The skill never re-implements the math; if the CLI drifts, so does the skill.

## Instructions

When the user runs `/harness score`:

1. Verify the CLI is installed:
   ```bash
   harness --version
   ```
   If it fails, tell the user to run `pip install agent-harness` and stop.

2. Verify `agent_logs/` exists in the current working directory. If not, tell
   the user to run `/harness init` first.

3. Run:
   ```bash
   harness score agent_logs --json-out
   ```
   The CLI writes `agent_logs/harness_score.md` and `agent_logs/harness_score.json`.

4. Read `agent_logs/harness_score.json` and present a concise summary to the user:
   - The composite score and grade
   - One-line breakdown of each of the 6 metrics
   - Total tool calls, steps, and wasted lines
   - Negative vs positive intervention count

5. Point the user at `agent_logs/harness_score.md` for the full report.

Do not compute the score manually — always go through the CLI.
