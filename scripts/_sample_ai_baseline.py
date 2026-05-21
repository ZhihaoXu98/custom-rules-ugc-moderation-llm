"""One-shot stratified sampler: writes 50 Civil Comments candidates for the AI baseline.

Why this exists: audit_session.py uses uniform shuffle + length filter, which yields
~95% benign political-aphorism rows because CC's mean toxicity is ~0.05. That sample
doesn't exercise the progamer_chat rule set (R2/R4/R5 in particular). This sampler
buckets the stream and over-samples the cells where the rules actually have to fire.

Buckets (priority order — a row that qualifies for multiple buckets goes to the first):
    identity_attack >= 0.4   → 10 rows (R2: slurs)
    threat          >= 0.4   →  7 rows (R4: credible threats)
    sexual_explicit >= 0.4   →  5 rows (R5: sexual content)
    toxicity        >= 0.7   → 13 rows (R1 permissiveness vs harassment)
    0.3 <= toxicity < 0.7    → 10 rows (boundary cases)
    toxicity        <  0.3   →  5 rows (clean baseline)

Length filter matches audit_session.py under chat regime (5-1000 chars, <150).

Output: data/audit/.ai_baseline_inbox.jsonl (one candidate per line). Subsequent
labeling step reads this file and produces data/audit/week1.ai_baseline.jsonl.

Usage:
    uv run python scripts/_sample_ai_baseline.py
"""

import json
import sys
from pathlib import Path
from typing import Any

OUT_PATH = Path("data/audit/.ai_baseline_inbox.jsonl")
DATASET_ID = "google/civil_comments"
SPLIT = "train"
SEED = 4096
OVERSAMPLE_N = 25_000  # CC mean toxicity is low; we need a wide window for the high-tox buckets.

LEN_MIN = 5
LEN_MAX = 1000
CHAT_LEN_MAX = 150  # progamer_chat regime

TARGETS: dict[str, int] = {
    "identity_attack": 10,
    "threat": 7,
    "sexual_explicit": 5,
    "high_tox": 13,
    "mid_tox": 10,
    "low_tox": 5,
}

TOX_COLUMNS: tuple[str, ...] = (
    "toxicity",
    "threat",
    "obscene",
    "insult",
    "identity_attack",
    "severe_toxicity",
)


def _passes_length(text: str) -> bool:
    n = len(text)
    return LEN_MIN <= n <= LEN_MAX and n < CHAT_LEN_MAX


def _bucket(row: dict[str, Any]) -> str:
    ia = float(row.get("identity_attack") or 0.0)
    th = float(row.get("threat") or 0.0)
    sx = float(row.get("sexual_explicit") or 0.0)
    tx = float(row.get("toxicity") or 0.0)
    if ia >= 0.4:
        return "identity_attack"
    if th >= 0.4:
        return "threat"
    if sx >= 0.4:
        return "sexual_explicit"
    if tx >= 0.7:
        return "high_tox"
    if tx >= 0.3:
        return "mid_tox"
    return "low_tox"


def main() -> int:
    from datasets import load_dataset  # heavy import: defer

    print(f"streaming {DATASET_ID} (seed={SEED}, oversample={OVERSAMPLE_N})…", file=sys.stderr)
    ds = load_dataset(DATASET_ID, split=SPLIT, streaming=True)
    shuffled = ds.shuffle(seed=SEED, buffer_size=10_000)

    buckets: dict[str, list[dict[str, Any]]] = {k: [] for k in TARGETS}
    seen = 0

    for i, row in enumerate(shuffled):
        if seen >= OVERSAMPLE_N:
            break
        seen += 1
        text = row.get("text", "")
        if not _passes_length(text):
            continue
        b = _bucket(row)
        if len(buckets[b]) < TARGETS[b]:
            buckets[b].append({**row, "_stream_idx": i})
        if all(len(buckets[k]) >= TARGETS[k] for k in TARGETS):
            print(f"all buckets filled after {seen} rows", file=sys.stderr)
            break

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with OUT_PATH.open("w", encoding="utf-8") as f:
        for bname in TARGETS:  # preserve target order in output
            rows = buckets[bname]
            print(f"  {bname:<18} {len(rows):>2}/{TARGETS[bname]}", file=sys.stderr)
            for r in rows:
                out_row = {
                    "_stream_idx": r["_stream_idx"],
                    "bucket": bname,
                    "text": r["text"],
                    "hf_id": r.get("id"),
                    "features": {col: float(r.get(col) or 0.0) for col in TOX_COLUMNS},
                    "sexual_explicit": float(r.get("sexual_explicit") or 0.0),
                }
                f.write(json.dumps(out_row, ensure_ascii=False) + "\n")

    total = sum(len(v) for v in buckets.values())
    print(f"wrote {total} candidates to {OUT_PATH}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
