# Mac adaptations to the pre-flight gauntlet

Date started: 2026-05-20.
Hardware: MacBook Air M4, 10 cores (4P+6E), 16 GB unified memory, macOS 15.6.1.

The `prompt/00-README.md` gauntlet was written for Windows/WSL2 + RTX 4070 + CUDA. This file records the substitutions made for an Apple Silicon Mac. Once `docs/decisions.md` exists (Day 1 of Week 1), promote the load-bearing items below into formal decision-log entries.

## Strategy decisions

| Decision | Choice | Rationale |
|---|---|---|
| GPU strategy | **Full-cloud (Modal A100) for everything that needs CUDA.** Modal handles Wk 4-5 training *and* Wk 6 vLLM serving *and* Wk 7 latency work. | vLLM does not run on macOS at all. Keeps the README's production stack (vLLM + AWQ + xgrammar guided JSON) intact for the blog/interview pitch. Expected extra Modal cost: ~$30-50 above the README's $120 budget. |
| Python | **uv-managed Python 3.11** at the project root. | CLAUDE.md template requires it. Conda 3.13 stays on the system but is unused for this project. |
| Local inference | **None for production purposes.** | Anything that ships runs on the Modal-served stack. (MLX or llama.cpp could be used for ad-hoc exploration, but isn't part of the deliverable.) |
| Latency claims | Re-anchor to Modal A100 numbers, not a 4070. | The README's "p95 ~300ms on a 4070, ~80ms projected A100" framing flips: A100 becomes measured, 4070 becomes irrelevant. The cost ratio and rule-set flexibility claims hold across hardware. |

## Gauntlet item-by-item

| README step | Status on Mac |
|---|---|
| 1. `nvidia-smi`, `nvcc`, `torch.cuda.is_available()` | **Skipped.** Substituted with `torch.backends.mps.is_available() == True` (verified ✅). |
| 2. `uv` install | ✅ uv 0.10.0 already on system. |
| 3. Claude Code install + auth | ✅ 2.1.145 running. |
| 4. `uv tool install modal` + `modal token new` | ✅ modal installed. Auth pending Tony's interactive `modal token new`. |
| 5. `uv tool install wandb` + `wandb login` | ✅ wandb installed. Auth pending Tony's interactive `wandb login`. |
| 6. HF account + Qwen 2.5 7B Instruct terms + write token | ⏳ Tony's manual action. |
| 7. `.env` with API keys | ✅ `.env` + `.env.example` created, both gitignored (`.env` only). Tony fills in real values. |
| 8. Local vLLM smoke test | **Deferred to Week 6 on Modal A100.** vLLM does not support macOS. |

## Repo bootstrapping done (pre-Week 1)

- `git init` at the project directory (the home dir's stray `.git` is left alone — see `.claude/` memory).
- `.python-version` pins 3.11; `.venv/` created via `uv venv --python 3.11` → Python 3.11.14.
- `.gitignore` covers venv, env, model weights, wandb runs, data caches, frontend artifacts, toxic-content folder.
- `.env.example` (template, will be committed) + `.env` (placeholders, gitignored).

## Disk hygiene done

Freed ~5 GB by deleting redundant zips in `~/Downloads` (Backup 2025-08-23.zip, two NeetCode course zips). Free space went from 11 GB to 16 GB; APFS snapshots may release more later. Watch disk before Wk 6 (local model caches even at int4 are ~4 GB) and consider another cleanup pass then.

## Things to revisit

- **Latency framing.** README's interview pitch quotes 4070 p95 numbers. Update the pitch in the README and blog drafts once we have measured Modal A100 numbers (Wk 7).
- **vLLM smoke test on Modal.** Schedule a tiny throwaway Modal run in Wk 6 Day 1 — catching CUDA/flash-attn mismatches there instead of mid-training.
- **Disk monitor.** If free drops below ~15 GB during Wk 4+, prune `~/.cache/huggingface` and revisit Downloads.
