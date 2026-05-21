"""Smoketest: load ToxicChat via `datasets`, print schema + one toxic + one jailbreak example.

Verifies the Week 3 chat-regime supplement is reachable from HF Hub and the
expected toxicity/jailbreaking flags are present. Streams the train split of
`lmsys/toxic-chat` config `toxicchat0124` (~5k rows). Run:
`uv run python scripts/smoketest_toxic_chat.py`.

Exits 0 on success; exits 1 with a `FAIL toxic_chat: ...` line on stderr
otherwise. Idempotent — reuses the default HF cache.
"""

import statistics
import sys
from typing import Any

from datasets import load_dataset

DATASET_ID = "lmsys/toxic-chat"
CONFIG = "toxicchat0124"
SPLIT = "train"
N_ROWS = 5080


def _p95(xs: list[float]) -> float:
    return statistics.quantiles(xs, n=20)[-1]


def main() -> int:
    print(f"toxic_chat smoketest: streaming {CONFIG} split={SPLIT}, target<={N_ROWS} rows")

    try:
        ds = load_dataset(DATASET_ID, CONFIG, split=SPLIT, streaming=True)
    except Exception as err:
        print(f"FAIL toxic_chat: load_dataset failed: {err}", file=sys.stderr)
        return 1

    print(f"features: {ds.features}")

    user_lengths: list[float] = []
    toxic_count = 0
    jailbreak_count = 0
    both_count = 0
    toxic_example: dict[str, Any] | None = None
    jailbreak_example: dict[str, Any] | None = None
    rows_seen = 0

    try:
        for i, row in enumerate(ds):
            if i >= N_ROWS:
                break
            rows_seen = i + 1
            user_input = row["user_input"]
            toxicity = int(row["toxicity"])
            jailbreaking = int(row["jailbreaking"])
            user_lengths.append(float(len(user_input)))
            if toxicity:
                toxic_count += 1
                if toxic_example is None:
                    toxic_example = row
            if jailbreaking:
                jailbreak_count += 1
                if jailbreak_example is None:
                    jailbreak_example = row
            if toxicity and jailbreaking:
                both_count += 1
    except (KeyError, TypeError, ValueError) as err:
        print(f"FAIL toxic_chat: row {rows_seen} malformed: {err}", file=sys.stderr)
        return 1
    except Exception as err:
        print(
            f"FAIL toxic_chat: stream iteration failed at row {rows_seen}: {err}",
            file=sys.stderr,
        )
        return 1

    if rows_seen == 0:
        print("FAIL toxic_chat: stream yielded 0 rows", file=sys.stderr)
        return 1

    print(
        f"user_input length (chars): min={int(min(user_lengths))} "
        f"median={int(statistics.median(user_lengths))} "
        f"mean={statistics.mean(user_lengths):.1f} "
        f"p95={_p95(user_lengths):.0f} "
        f"max={int(max(user_lengths))}"
    )
    print(
        f"label rates: toxicity={toxic_count}/{rows_seen} "
        f"({100 * toxic_count / rows_seen:.2f}%) "
        f"jailbreaking={jailbreak_count}/{rows_seen} "
        f"({100 * jailbreak_count / rows_seen:.2f}%) "
        f"both={both_count}"
    )

    if toxic_example is not None:
        print("--- toxic example ---")
        print(f"user_input: {toxic_example['user_input']!r}")
        print(
            f"toxicity: {toxic_example['toxicity']}  jailbreaking: {toxic_example['jailbreaking']}"
        )
    else:
        print("note: no toxic examples encountered")

    if jailbreak_example is not None:
        print("--- jailbreak example ---")
        print(f"user_input: {jailbreak_example['user_input']!r}")
        print(
            f"toxicity: {jailbreak_example['toxicity']}  "
            f"jailbreaking: {jailbreak_example['jailbreaking']}"
        )
    else:
        print("note: no jailbreak examples encountered")

    print(f"OK   toxic_chat: {rows_seen} rows streamed, toxicity+jailbreaking flags present")
    return 0


if __name__ == "__main__":
    sys.exit(main())
