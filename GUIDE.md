# Testing & Publishing Guide

How to test the `harness` CLI, the three Claude Code skills, and push the package to PyPI.

---

## 1. Local dev setup

From the repo root (`D:\N Projects\Harness-Benchmark-Skill`):

```bash
python -m venv .venv
.venv\Scripts\activate            # Windows
# source .venv/bin/activate       # macOS/Linux

pip install -e ".[dev]"
```

`-e` installs in editable mode, so code edits take effect without reinstalling.
`[dev]` pulls in `pytest` + `pytest-cov`.

Verify:
```bash
harness --version        # -> 0.2.0
pytest -v                # -> 49 passed
```

---

## 2. Testing the CLI

### 2a. Unit tests (fastest)
```bash
pytest -v
pytest --cov=harness --cov-report=term-missing   # with coverage
pytest tests/test_cli.py -v                      # CLI only
```

### 2b. Manual smoke test — full workflow
```bash
mkdir sandbox && cd sandbox

# 1. Scaffold
harness init agent_logs
# Creates agent_logs/trace.md, tool_calls.json, diff_summary.md, session_meta.json

# 2. Populate (normally done by an agent via /harness log)
#    Edit the three log files with real step data, or copy ../examples/auto_eda/*

# 3. Score
harness score agent_logs --json-out
# Writes agent_logs/harness_score.md + harness_score.json

# 4. CI gate
harness score agent_logs --fail-below 0.70
echo $?   # 0 if >= 0.70, 1 if below
```

### 2c. Error paths
```bash
harness score does_not_exist        # -> "directory not found", exit 1
harness score empty_dir             # -> "missing required files", exit 1
```

### 2d. Hook capture
```bash
# Simulate what Claude Code sends on PostToolUse
echo '{"tool_name":"Read","tool_input":{"file_path":"x.py"},"tool_response":{"content":"ok"}}' \
  | python -m harness.hook_capture

cat agent_logs/tool_calls.json   # should contain the appended entry
```

### 2e. Version enforcement
Edit `agent_logs/session_meta.json` → set `"harness_version": "2.0"` → run
`harness score agent_logs`. You should get a `HarnessVersionError` — confirms
future breaking-schema versions are rejected.

---

## 3. Testing the skills (Claude Code)

The skills live in `skills/` as `harness-init.md`, `harness-log.md`, `harness-score.md`.
Claude Code discovers skills from either your user dir or a project's `.claude/skills/`.

### 3a. Install locally for testing
```bash
# User-level (available in every project):
mkdir -p ~/.claude/skills
cp skills/harness-*.md ~/.claude/skills/

# OR project-level (only in the test project):
mkdir -p /path/to/test-project/.claude/skills
cp skills/harness-*.md /path/to/test-project/.claude/skills/
```

Windows paths: `%USERPROFILE%\.claude\skills\`.

### 3b. Run through the skills in a fresh project
```bash
cd /path/to/test-project
claude        # launch Claude Code
```

Inside the session:
1. `/harness init` — scaffolds `agent_logs/`. Confirm all 4 files exist.
2. Do some real work (ask Claude to build a small feature, edit files, run commands).
3. `/harness log` — confirm new STEP blocks are appended to all three log files.
4. `/harness score` — confirm `harness_score.md` + `.json` are written and the
   summary is posted in chat.

### 3c. Install the PostToolUse hook (unbiased logging)
Add to `.claude/settings.json` in the test project:
```json
{
  "hooks": {
    "PostToolUse": [{
      "matcher": "Write|Edit|Read|Bash|Glob|Grep|NotebookEdit",
      "hooks": [{ "type": "command", "command": "python -m harness.hook_capture" }]
    }]
  }
}
```
Open `/hooks` in Claude Code once to reload config. After any tool call,
`agent_logs/tool_calls.json` should grow automatically.

### 3d. What to watch for
- Skill files must be copied, not symlinked on Windows (Claude Code won't resolve).
- `/harness init` should fail gracefully if `harness` isn't on PATH — confirms the
  skill delegates instead of reimplementing.
- `/harness score` should never do math itself; it shells out to `harness score`.

---

## 4. Publishing to PyPI

### 4a. One-time setup
1. Register accounts: https://pypi.org/account/register and https://test.pypi.org/account/register.
2. Enable 2FA on both.
3. Create API tokens: PyPI → Account settings → API tokens → "Add token" (scope: entire account for the first upload, scope to project after).
4. Pick a package name that's not taken — search https://pypi.org/project/agent-harness/. If taken, rename in `pyproject.toml`.
5. Update `[project.urls]` in `pyproject.toml` — replace `YOUR_USERNAME` with your GitHub handle.

### 4b. Build tools
```bash
pip install --upgrade build twine
```

### 4c. Build the distribution
```bash
# From repo root
rm -rf dist build *.egg-info      # Windows: rmdir /s /q dist build
python -m build
# -> dist/agent_harness-0.2.0.tar.gz
# -> dist/agent_harness-0.2.0-py3-none-any.whl
```

Sanity-check the wheel:
```bash
twine check dist/*
```

### 4d. Upload to TestPyPI first (always)
```bash
twine upload --repository testpypi dist/*
# username: __token__
# password: <paste TestPyPI token, including the `pypi-` prefix>
```

Install from TestPyPI in a clean venv to verify:
```bash
python -m venv /tmp/verify && source /tmp/verify/bin/activate
pip install --index-url https://test.pypi.org/simple/ \
            --extra-index-url https://pypi.org/simple/ \
            agent-harness
harness --version
harness init /tmp/logs
```

### 4e. Upload to real PyPI
```bash
twine upload dist/*
# username: __token__
# password: <PyPI token>
```

Done. Users can now `pip install agent-harness`.

### 4f. Storing credentials (optional)
Create `~/.pypirc`:
```ini
[pypi]
  username = __token__
  password = pypi-AgEI...YOUR_TOKEN

[testpypi]
  repository = https://test.pypi.org/legacy/
  username = __token__
  password = pypi-AgEI...YOUR_TESTPYPI_TOKEN
```
Set perms: `chmod 600 ~/.pypirc` (on Windows, restrict via file properties).

### 4g. Releasing a new version
1. Bump `version` in `pyproject.toml` AND `__version__` in `harness/__init__.py`.
2. If the log-file schema changed: bump `SCHEMA_VERSION` in `harness/constants.py`.
   - Patch change in content only → keep major (e.g. `"1.0"` → `"1.1"`).
   - Breaking change → bump major (e.g. `"1.0"` → `"2.0"`); old logs will be rejected by `check_version()`.
3. Update CHANGELOG (add one if you don't have it yet).
4. `git tag v0.3.0 && git push --tags`.
5. Rebuild + upload (4c → 4e).
6. Optional: create a GitHub Release from the tag.

### 4h. Automating via GitHub Actions (optional)
Add a `release.yml` workflow triggered on tag push, using PyPI's trusted
publishing (OIDC) — no tokens needed. See
https://docs.pypi.org/trusted-publishers/ for the setup steps.

---

## 5. Pre-publish checklist

- [ ] `pytest` passes on all three OSes (CI already covers this)
- [ ] `harness --version` returns the new version
- [ ] Package name on PyPI is available / owned by you
- [ ] `pyproject.toml` URLs point at the real repo
- [ ] README renders on PyPI (run `twine check dist/*`)
- [ ] LICENSE file included in the sdist (setuptools does this by default)
- [ ] Uploaded to TestPyPI and installed cleanly in a fresh venv
- [ ] Tag pushed to GitHub matches the PyPI version
