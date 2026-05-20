# Daily workflow on the M4 Air

Companion to `prompt/00-README.md` § "How to work with Claude Code". Read that first — this file only adds Mac-specific details and the concrete daily routine.

## Starting a session

```bash
cd "/Users/tonyxu/Desktop/Custom-Rules UGC Moderation LLM"
claude           # opens Claude Code in the project repo
```

In the first message of a new session, tell Claude Code which week you're on:

> "Read `prompt/0X-week-XX.md` and `docs/decisions.md`. We're on Day Y. Don't start work yet — just confirm what's planned."

Claude Code will auto-read `CLAUDE.md` on session start (once it exists, Day 1 of Wk 1).

## Per-session rhythm

1. **Plan-mode prompt** for any multi-file or schema/prompt/data change. Review the plan, push back, then `Approve. Execute.`
2. **Execution prompt** for small fixes, follow-ups, well-defined scripts.
3. After every meaningful change: `/lint` (Wk 1+).
4. Commit via `/checkpoint` (Wk 1+) — never autocommit.
5. **`/clear` between weeks**, and between major task switches inside a week.

## When you're invoking Modal (Wk 4+)

Because everything that needs CUDA runs on Modal:

- Before any Modal run, ask Claude Code to estimate cost. If it doesn't, push back.
- After every Modal run, log spend mentally; weekly cap is $20.
- `modal app list` shows running apps. `modal app stop <name>` kills runaways.
- Modal runs that crash mid-train still bill for elapsed time — kill them fast.

## Content exposure (README's rules, repeated because they're load-bearing)

- 30-minute sessions max when auditing/labeling toxic content. Timer on.
- 90+ minutes between sessions.
- No audit sessions after 8 pm.
- One zero-exposure day each week.

## Sanity checks before any commit

```bash
git status                       # confirm only intended files are staged
cat .gitignore                   # confirm .env is still listed
grep -r "sk-\|hf_\|wandb_" src/ tests/ scripts/ 2>/dev/null   # no hardcoded keys
```

## When something feels off

- **Wrong git repo.** Run `git rev-parse --show-toplevel`. It MUST print the project dir, not `/Users/tonyxu`. If it prints the home dir, the project `.git` was deleted — recreate it.
- **Wrong Python.** Run `uv run python --version`. Must be 3.11.x. If it's 3.13, you're in the conda env — `deactivate` and re-cd.
- **Disk pressure.** `df -h /` — if free < 15 GB, prune `~/.cache/huggingface` and old Downloads.

## What a "good day" looks like

~2 hours, one or two PRs of progress: one plan-mode prompt approved + executed, one execution prompt for follow-up fixes, /lint clean, /checkpoint committed, decision-log entry written in your voice if the day produced a real choice.

A "great day" includes a postmortem entry (Wk 4+) if something broke and you learned something.
