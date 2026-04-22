# /harness log

Append the current step's data to all three agent log files.

## What this does

At the end of each agent step, updates:
- `agent_logs/trace.md` — appends a new STEP block
- `agent_logs/tool_calls.json` — appends tool call entries for this step
- `agent_logs/diff_summary.md` — appends a diff entry for this step

## Instructions

When the user runs `/harness log`:

1. Determine the current step number by counting existing STEP blocks in `agent_logs/trace.md`.
   The new step number = existing count + 1.

2. Reflect on the work just completed in this turn and extract:
   - **GOAL**: What was the objective of this step?
   - **FILES READ**: List of files read (from Read tool calls)
   - **FILES MODIFIED**: List of files written/edited (from Write/Edit tool calls)
   - **TOOLS USED**: List of tools used with brief description
   - **DECISION**: Key decisions made and why
   - **RESULT**: What actually happened — success, partial, or failure
   - **NEXT PLAN**: What comes next
   - **PHASE**: One of: SCAFFOLD, BUILD, DEBUG, VERIFY, PLAN, MAINTAIN, FAILED

3. Append to `agent_logs/trace.md`:
```
---

STEP: {N}

GOAL:
{goal}

FILES READ:
{files_read as bullet list, or "None"}

FILES MODIFIED:
{files_modified as bullet list}

TOOLS USED:
{tools as bullet list}

DECISION:
{decision}

RESULT:
{result}

NEXT PLAN:
{next_plan}

---
```

4. For each tool call made in this step, append a JSON object to `agent_logs/tool_calls.json`:
```json
{
  "step": {N},
  "tool": "{tool_name}",
  "input": "{brief description of what was passed}",
  "output_summary": "{what the tool returned or did}",
  "timestamp": "{ISO timestamp}"
}
```
Read the existing JSON array, append new entries, write back the full array.

5. Append to `agent_logs/diff_summary.md`:
```
---

STEP: {N}
FILES CHANGED: {comma-separated list}
LINES ADDED: {count}
LINES REMOVED: {count}
REASON FOR CHANGE: {one-sentence reason}

---
```
Estimate lines added/removed from the files written/edited in this step.

6. If the user asked you to redirect, correct, or cancel something this step, also append
   a user intervention to `agent_logs/session_meta.json`:
```json
{
  "step": {N},
  "prompt": "{the user's intervention text}",
  "type": "negative",
  "reason": "{why it was a correction or redirect}"
}
```
If the user added new scope or approved work, use `"type": "positive"`.

7. Confirm: "Step {N} logged."
