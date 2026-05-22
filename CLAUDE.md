# CLAUDE.md — project conventions

## Project
Custom-rules UGC moderation LLM. Fine-tune Qwen 2.5 7B for rule-set-conditional
judgment of chat and comments. The Pareto pitch: 5-20× faster than frontier
APIs and 30-100× cheaper while preserving rule-set flexibility that fixed
classifiers (Perspective, OpenAI Moderation, Hive) can't match. Serve via
AWQ INT4 + vLLM + guided JSON. Measured on RTX 4070 12GB (chat p95 ~300ms,
~80ms projected A100); the cost ratio and flexibility claim hold across GPUs.

## Stack
- Python 3.11 via `uv` (NOT conda, NOT pip directly)
- Pydantic v2 (NOT v1)
- mypy --strict on src/
- Ruff for lint + format (line length 100)
- vLLM 0.6+ for serving
- TRL + PEFT for SFT/DPO
- Modal A100 40GB for training
- FastAPI + Pydantic v2 for API
- Next.js + Tailwind + shadcn/ui for frontend

## File layout (canonical)
src/         — production code (mypy --strict)
tests/       — pytest tests (typing lighter OK)
scripts/     — one-off + admin scripts
data/        — datasets (mosed)
docs/        — markdown docs
frontend/    — Next.js demo app
.github/workflows/ — CI
.claude/commands/  — slash commands

## Pinned contracts (do NOT change without explicit approval)
- src/schema.py — Pydantic models for Judgment, RuleSet, Content.
  Changes require retraining and re-eval.
- src/prompts.py — canonical prompt template. Training and inference MUST
  use this same module.
- data/HELD_OUT.txt — IDs that must never appear in training data.
  CI enforces this.
- data/golden_eval.jsonl — locked after Week 2. Any change is a new version
  with a fresh baseline re-run.

## Pinned contracts (Week 1)
- src/schema.py — locked from Day 2. Changes require retraining and re-eval.
- data/rule_sets/*.yaml — the 5 hand-written sets are exemplars; LLM-generated
  rule sets in Week 3 will be audited individually before joining the catalog.
- docs/decisions.md — never modify without my approval; I write every entry.

## Documents I write (NOT you)
- docs/decisions.md — every entry is mine. You may suggest content;
  I write prose.
- docs/postmortems.md — same.
- docs/model_card.md (Week 10) — outline + copy-edit only.
- Blog post (Week 11) — outline + copy-edit only. Do not draft paragraphs.

## Cost discipline
- API calls (OpenAI, Anthropic): confirm with me before any single script
  that may exceed $1; hard-warn atal A100: estimate cost before any run; confirm if > $1; cap $20/week.

## Verification expected after every meaningful change
- `uv run ruff check && uv run ruff format --check`
- `uv run mypy src/`
- `uv run pytest`
- If touching the model: a regression-eval slice (Week 10+)

## Things to NEVER do without explicit confirmation
- Commit or push without me approving
- Modify docs/decisions.md, docs/postmortems.md, docs/model_card.md
- Modify src/schema.py or src/prompts.py
- Modify data/HELD_OUT.txt or data/golden_eval.jsonl
- Add a dependency without confirming the version (web-search current)
- Delete anything from data/, .env, .git
- Run a script that incurs > $1 API cost without confirming
- Hardcode an API key anywhere

## Mode preferences
- Multi-file changes, design decisions, pinned-contract touches: PLAN-MODE.
- Small fixes, doc updates, test additions, post-plan execution: EXECUTION.
- I'll explicitly say "YOLO this" for the rare bulk-fixture cases.

## Web search
You can and should web-search for current library versions, recent benchmarks,
current best practices. Especially: vLLM, TRL, PEFT, AutoAWQ, xgrammar, Langfuse —
all evolve fast. Search before pinning versions or recommending models.

## Style
- Type-hint everything in src/. Best-effort in tests/scripts/.
- Pydantic models in src/schema.py only; no ad-hoc dataclasses.
- Configuration via pydantic-settings BaseSettings, not argparse.
- Async by default for I/O code.
- Logging via stdlib `logging`, not `print`.
- Raise specific exceptions; don't swallow.
