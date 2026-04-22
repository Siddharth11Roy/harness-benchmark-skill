# /harness init

Scaffold the `agent_logs/` directory with empty harness log templates.

## What this does

Delegates to the `harness` CLI so the on-disk format always matches the parser.

## Instructions

When the user runs `/harness init`:

1. Check that the CLI is installed:
   ```bash
   harness --version
   ```
   If not installed, tell the user: `pip install agent-harness` and stop.

2. Run:
   ```bash
   harness init agent_logs
   ```
   This creates:
   - `agent_logs/trace.md`
   - `agent_logs/tool_calls.json`
   - `agent_logs/diff_summary.md`
   - `agent_logs/session_meta.json` (with current harness_version, today's date, current model)

3. Ask the user if they want you to fill in `project` (current directory name) and
   `task_prompt` (the task they originally gave you) in `session_meta.json`.
   If yes, read the file, update those two fields, write it back.

4. Recommend they also install the PostToolUse hook for unbiased logging:

   Add to `.claude/settings.json`:
   ```json
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
   ```

5. Tell them to run `/harness log` after each logical step and `/harness score`
   at the end of the session.
