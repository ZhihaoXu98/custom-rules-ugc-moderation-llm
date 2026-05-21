"""Smoketest: load Civil Comments via `datasets`, print schema + one high-tox example.

Verifies the Week 3 primary corpus is reachable from HF Hub and the expected
toxicity features are present. Streams 1000 rows from the train split so the
full ~500 MB parquet never materializes locally. Run:
`uv run python scripts/smoketest_civil_comments.py`.

Exits 0 on success; exits 1 with a `FAIL civil_comments: ...` line on stderr
otherwise. Idempotent — re-running reuses the default HF cache and writes
nothing under data/.
"""

import statistics
import sys
from typing import Any

from datasets import load_dataset

DATASET_ID = "google/civil_comments"
SPLIT = "train"
N_ROWS = 1000
TOX_THRESHOLD = 0.7


def _p95(xs: list[float]) -> float:
    return statistics.quantiles(xs, n=20)[-1]


def main() -> int:
    print(f"civil_comments smoketest: streaming split={SPLIT}, target={N_ROWS} rows")

    try:
        ds = load_dataset(DATASET_ID, split=SPLIT, streaming=True)
    except Exception as err:
        print(f"FAIL civil_comments: load_dataset failed: {err}", file=sys.stderr)
        return 1

    print(f"features: {ds.features}")

    lengths: list[float] = []
    toxicities: list[float] = []
    high_tox_row: dict[str, Any] | None = None
    highest_seen_tox = -1.0
    highest_seen_row: dict[str, Any] | None = None
    rows_seen = 0

    try:
        for i, row in enumerate(ds):
            if i >= N_ROWS:
                break
            rows_seen = i + 1
            text = row["text"]
            toxicity = float(row["toxicity"])
            lengths.append(float(len(text)))
            toxicities.append(toxicity)
            if high_tox_row is None and toxicity > TOX_THRESHOLD:
                high_tox_row = row
            if toxicity > highest_seen_tox:
                highest_seen_tox = toxicity
                highest_seen_row = row
    except (KeyError, TypeError, ValueError) as err:
        print(f"FAIL civil_comments: row {rows_seen} malformed: {err}", file=sys.stderr)
        return 1
    except Exception as err:
        print(
            f"FAIL civil_comments: stream iteration failed at row {rows_seen}: {err}",
            file=sys.stderr,
        )
        return 1

    if rows_seen == 0:
        print("FAIL civil_comments: stream yielded 0 rows", file=sys.stderr)
        return 1

    print(
        f"text length (chars): min={int(min(lengths))} "
        f"median={int(statistics.median(lengths))} "
        f"mean={statistics.mean(lengths):.1f} "
        f"p95={_p95(lengths):.0f}"
    )
    print(
        f"toxicity:            min={min(toxicities):.3f} "
        f"median={statistics.median(toxicities):.3f} "
        f"p95={_p95(toxicities):.3f}"
    )

    example = high_tox_row if high_tox_row is not None else highest_seen_row
    if high_tox_row is None:
        print(f"note: no row > {TOX_THRESHOLD} in {rows_seen}-row sample; showing highest")

    if example is not None:
        print("---")
        print(f"text:            {example['text']!r}")
        print(f"toxicity:        {float(example['toxicity']):.3f}")
        print(f"severe_toxicity: {float(example['severe_toxicity']):.3f}")
        print(f"insult:          {float(example['insult']):.3f}")
        print(f"threat:          {float(example['threat']):.3f}")
        print("---")

    print(f"OK   civil_comments: {rows_seen} rows streamed, toxicity features present")
    return 0


if __name__ == "__main__":
    sys.exit(main())
