---
description: Run ruff check, ruff format --check, mypy --strict, pytest. Stop on first failure; do not auto-fix.
allowed-tools: Bash(uv run ruff check), Bash(uv run ruff format --check), Bash(uv run mypy src/), Bash(uv run pytest)
---

Run the project verification chain. Execute these four commands in order, **stopping at the first failure**:

1. `uv run ruff check`
2. `uv run ruff format --check`
3. `uv run mypy src/`
4. `uv run pytest`

**If any step fails:**
- STOP immediately. Do not run subsequent steps.
- Report which step failed and paste the relevant output (trim noise; keep the error).
- Do NOT attempt to fix the failure. Ask whether to proceed with a fix before making any edits.

**If all four pass:** report exactly `All checks pass.` and nothing else.
