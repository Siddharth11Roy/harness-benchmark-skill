# agent-harness

Benchmark any AI agent session by scoring structured log files.

Works with Claude Code, Cursor, Blackbox, Copilot — any agent that writes code.

---

## Harness Score

```
H = 0.30×C + 0.18×E + 0.15×T + 0.15×R + 0.12×D + 0.10×P
```

| Metric | What it measures |
|---|---|
| **C** Completion | Did the agent finish all tasks? |
| **E** Efficiency | How many steps per completed task? |
| **T** Tool Success | What % of tool calls succeeded? |
| **R** Recovery | Did the agent recover from every error? |
| **D** Diff Quality | How much code was written then thrown away? |
| **P** Planning Quality | Did the agent read before writing? |

---

## Log Files

Four files live in your `agent_logs/` directory:

| File | Purpose |
|---|---|
| `trace.md` | Step-by-step trace: goal, files, tools, decision, result |
| `tool_calls.json` | Every tool invocation with input/output summary |
| `diff_summary.md` | Per-step: lines added/removed, files changed, reason |
| `session_meta.json` | Model, date, build success, user interventions |

### session_meta.json — Prompt Classification

User interventions are classified as **negative** or **positive**:

- **negative** — redirect, cancel, correction, rejection of output
- **positive** — new scope added, approval, extension of current approach

```json
{
  "user_interventions": [
    {
      "step": 10,
      "prompt": "Stop, this is too slow, use React instead",
      "type": "negative",
      "reason": "redirect — user cancelled running task"
    }
  ]
}
```

---

## Claude Code Skills

Three skills for use inside Claude Code sessions:

### `/harness init`
Scaffolds `agent_logs/` with empty templates at the start of a session.

### `/harness log`
Appends the current step's data to all log files. Run this after each agent step.

### `/harness score`
Reads all logs, computes the harness score, and writes `agent_logs/harness_score.md`.

---

## CLI

```bash
pip install agent-harness
```

```bash
# Score a session
harness score ./agent_logs

# Score with JSON output
harness score ./agent_logs --json-out

# Fail CI if score < 0.70
harness score ./agent_logs --fail-below 0.70

# Scaffold empty logs
harness init agent_logs
```

### CI/CD (GitHub Actions)

```yaml
- name: Benchmark agent session
  run: harness score ./agent_logs --fail-below 0.70
```

---

## Example

See `examples/auto_eda/` — a real benchmark from a Blackbox AI session that built
a full Auto-EDA platform (React + Flask + Celery). Final score: **0.846 / B+**.

---

## Grade Reference

| Score | Grade | Description |
|---|---|---|
| 0.90+ | A | Excellent — minimal waste, perfect recovery |
| 0.80+ | B+ | Strong — minor inefficiencies, good recovery |
| 0.70+ | B | Good — some wandering, decent recovery |
| 0.60+ | C | Average — noticeable waste, partial recovery |
| <0.60 | D | Weak — significant looping, poor recovery |

---

## Install Skills in Claude Code

Copy the skill files to your Claude skills directory:

```bash
cp skills/harness-init.md ~/.claude/skills/
cp skills/harness-log.md ~/.claude/skills/
cp skills/harness-score.md ~/.claude/skills/
```

Then use `/harness init`, `/harness log`, `/harness score` in any Claude Code session.

---

MIT License
