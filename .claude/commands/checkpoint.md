---
description: Lint-gated conventional commit. Runs /lint, stages all, commits. Never pushes.
allowed-tools: Bash(uv run ruff check), Bash(uv run ruff format --check), Bash(uv run mypy src/), Bash(uv run pytest), Bash(git add -A), Bash(git status), Bash(git diff --cached --stat), Bash(git commit -m:*), Bash(git log:*)
---

Checkpoint the current working tree. **Never push under any circumstance.**

### Step 1 — Lint gate (same chain as /lint)

Run in order, stop on first failure:
1. `uv run ruff check`
2. `uv run ruff format --check`
3. `uv run mypy src/`
4. `uv run pytest`

If any check fails: **REFUSE to commit.** Report which step failed and exit. Do not stage. Do not commit.

### Step 2 — Stage and summarize

- `git add -A`
- `git diff --cached --stat` — print the one-line-per-file diff summary
- `git status` — confirm what's staged

If nothing is staged after `git add -A`: report "No changes to commit." and exit.

### Step 3 — Conventional commit

Generate a message using exactly one of these types: `feat` / `fix` / `docs` / `chore` / `refactor` / `test`.

Format:
- Title: `<type>(<optional-scope>): <imperative, lower-case, ≤72 chars>`
- Optional body: 1–2 sentences focused on **why**, not what.
- **Do NOT add a `Co-Authored-By` trailer.**

Print the proposed message, then commit via heredoc:

```bash
git commit -m "$(cat <<'EOF'
<type>(<scope>): <subject>

<optional why-focused body>
EOF
)"
```

After commit: run `git status` to confirm clean tree. **Do not run `git push`.**
