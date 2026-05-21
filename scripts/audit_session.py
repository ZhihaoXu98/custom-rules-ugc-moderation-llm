"""Interactive single-session audit: human labels Civil Comments under a rule set.

Loads a rule set + Civil Comments via `datasets`, prompts the auditor for the 8
`Judgment` fields per candidate, validates, and appends to `data/audit/week1.jsonl`.

Session discipline (enforced, not optional):
- 30-minute hard cap; warn at 25 min; refuse new candidates after 30.
- 3 distressing-content skips per session; the 4th ends the session with a
  "go take a break" message.
- 90-minute cooldown after a finished session before a new one can start.
- Resume support: a partial session (process killed mid-run) can be picked up
  exactly where it left off, by re-deriving the candidate stream from the
  saved seed and skipping past the cursor.

Use --dev to iterate on the script itself (writes to data/audit/week1.dev.jsonl
and data/audit/.sessions.dev/, bypasses the cooldown). Do NOT use --dev for
real audit sessions; rows tagged dev_mode=true.

Usage:
    uv run python scripts/audit_session.py [--rule-set SLUG] [--n N] [--seed K] [--dev]

Exits 0 on graceful end (target reached, time cap, skip limit, user quit);
1 on configuration errors (unknown rule set, dataset load failure, cooldown
block, no candidates after filtering); 130 on KeyboardInterrupt.
"""

import argparse
import json
import logging
import os
import sys
import time
import uuid
from collections.abc import Callable, Mapping
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from src.schema import (
    Judgment,
    PrimaryCategory,
    Regime,
    RuleSet,
    Severity,
    SuggestedAction,
)

logger = logging.getLogger("audit_session")

# ─── Paths ───
AUDIT_DIR = Path("data/audit")
AUDIT_FILE = AUDIT_DIR / "week1.jsonl"
SESSIONS_DIR = AUDIT_DIR / ".sessions"
DEV_AUDIT_FILE = AUDIT_DIR / "week1.dev.jsonl"
DEV_SESSIONS_DIR = AUDIT_DIR / ".sessions.dev"
RULE_SETS_DIR = Path("data/rule_sets")

# ─── Session limits ───
SESSION_HARD_CAP_MIN = 30
SESSION_WARN_MIN = 25
COOLDOWN_MIN = 90
MAX_SKIPS = 3
RETRY_CAP = 3

# ─── Dataset sampling ───
DATASET_ID = "google/civil_comments"
DATASET_SPLIT = "train"
OVERSAMPLE_N = 200
LEN_MIN = 5
LEN_MAX = 1000
CHAT_LEN_MAX = 150
TOX_COLUMNS: tuple[str, ...] = (
    "toxicity",
    "threat",
    "obscene",
    "insult",
    "identity_attack",
    "severe_toxicity",
)


# ─────────────────────────── Time helpers ───────────────────────────


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def _parse_iso(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def _elapsed_min(start_iso: str) -> float:
    return (datetime.now(UTC) - _parse_iso(start_iso)).total_seconds() / 60.0


# ─────────────────────────── Session state ──────────────────────────


@dataclass
class SessionState:
    session_id: str
    rule_set_slug: str
    target_n: int
    n_completed: int
    cursor: int
    skips_used: int
    seed: int
    started_at: str
    last_activity_at: str
    ended_at: str | None
    ended_reason: str | None
    warned_25min: bool
    dev_mode: bool

    @classmethod
    def new(
        cls,
        *,
        rule_set_slug: str,
        target_n: int,
        seed: int,
        dev_mode: bool,
    ) -> "SessionState":
        now = _utc_now_iso()
        return cls(
            session_id=uuid.uuid4().hex[:12],
            rule_set_slug=rule_set_slug,
            target_n=target_n,
            n_completed=0,
            cursor=0,
            skips_used=0,
            seed=seed,
            started_at=now,
            last_activity_at=now,
            ended_at=None,
            ended_reason=None,
            warned_25min=False,
            dev_mode=dev_mode,
        )


def _sessions_dir(dev: bool) -> Path:
    return DEV_SESSIONS_DIR if dev else SESSIONS_DIR


def _audit_file(dev: bool) -> Path:
    return DEV_AUDIT_FILE if dev else AUDIT_FILE


def save_session_state(s: SessionState) -> None:
    d = _sessions_dir(s.dev_mode)
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{s.session_id}.json").write_text(json.dumps(asdict(s), indent=2))


def load_session_state(path: Path) -> SessionState:
    return SessionState(**json.loads(path.read_text()))


def find_latest_session(dev: bool) -> SessionState | None:
    d = _sessions_dir(dev)
    if not d.exists():
        return None
    files = sorted(d.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    for path in files:
        try:
            return load_session_state(path)
        except (OSError, json.JSONDecodeError, TypeError) as e:
            logger.warning("skipping unreadable session file %s: %s", path, e)
    return None


def cooldown_remaining_min(last: SessionState) -> float:
    if last.ended_at is None:
        return 0.0
    elapsed = (datetime.now(UTC) - _parse_iso(last.ended_at)).total_seconds() / 60.0
    return max(0.0, COOLDOWN_MIN - elapsed)


def is_resumable(s: SessionState, rule_set_slug: str) -> bool:
    return s.ended_at is None and s.n_completed < s.target_n and s.rule_set_slug == rule_set_slug


# ──────────────────────── Rule set / candidates ─────────────────────


def load_rule_set(slug: str) -> RuleSet:
    path = RULE_SETS_DIR / f"{slug}.yaml"
    if not path.exists():
        raise FileNotFoundError(f"rule set file not found: {path}")
    data = yaml.safe_load(path.read_text())
    rs = RuleSet.model_validate(data)
    if rs.slug != slug:
        raise ValueError(f"slug {rs.slug!r} != filename stem {slug!r}")
    return rs


def _passes_length(text: str, regime: Regime) -> bool:
    n = len(text)
    if not (LEN_MIN <= n <= LEN_MAX):
        return False
    return not (regime is Regime.chat and n >= CHAT_LEN_MAX)


def load_candidates(seed: int, regime: Regime) -> list[dict[str, Any]]:
    from datasets import load_dataset  # heavy import: defer

    ds = load_dataset(DATASET_ID, split=DATASET_SPLIT, streaming=True)
    shuffled = ds.shuffle(seed=seed, buffer_size=10_000)

    raw: list[dict[str, Any]] = []
    for i, row in enumerate(shuffled):
        if len(raw) >= OVERSAMPLE_N:
            break
        raw.append({**row, "_stream_idx": i})

    return [r for r in raw if _passes_length(r["text"], regime)]


# ───────────────────────────── Prompts ──────────────────────────────


def prompt_violates_policy() -> bool:
    while True:
        v = input("violates_policy [y/n]: ").strip().lower()
        if v in ("y", "yes", "true", "1"):
            return True
        if v in ("n", "no", "false", "0"):
            return False
        print("  please enter y or n")


def prompt_violated_rules(rs: RuleSet) -> list[str]:
    valid = {r.id for r in rs.rules}
    while True:
        v = input(f"violated_rules (comma-separated, valid={sorted(valid)}; empty=none): ").strip()
        if not v:
            return []
        ids = [s.strip() for s in v.split(",") if s.strip()]
        unknown = [i for i in ids if i not in valid]
        if unknown:
            print(f"  unknown ids: {unknown}; try again")
            continue
        if len(ids) != len(set(ids)):
            print("  duplicate ids; try again")
            continue
        if len(ids) > 10:
            print(f"  too many ({len(ids)}); max 10")
            continue
        return ids


def prompt_enum(name: str, enum_cls: type[Severity | PrimaryCategory | SuggestedAction]) -> str:
    options = list(enum_cls)
    print(f"{name}:")
    for i, opt in enumerate(options, 1):
        print(f"  {i}. {opt.value}")
    while True:
        v = input(f"  choose 1-{len(options)} or type value: ").strip().lower()
        if v.isdigit() and 1 <= int(v) <= len(options):
            return str(options[int(v) - 1].value)
        for opt in options:
            if v == opt.value:
                return str(opt.value)
        print("  invalid; try again")


def prompt_evidence_spans() -> list[str]:
    print("evidence_spans (one per line, blank to finish, max 5, each 1-300 chars):")
    spans: list[str] = []
    while len(spans) < 5:
        v = input(f"  [{len(spans) + 1}] ").strip()
        if not v:
            break
        if not (1 <= len(v) <= 300):
            print(f"    invalid length ({len(v)}); try again")
            continue
        spans.append(v)
    return spans


def prompt_confidence() -> float:
    while True:
        v = input("confidence [0.0-1.0]: ").strip()
        try:
            f = float(v)
        except ValueError:
            print("  not a number; try again")
            continue
        if not (0.0 <= f <= 1.0):
            print("  out of range; try again")
            continue
        return f


def prompt_reasoning() -> str:
    while True:
        v = input("reasoning (1-400 chars): ").strip()
        if not (1 <= len(v) <= 400):
            print(f"  invalid length ({len(v)}); try again")
            continue
        return v


PROMPTERS: Mapping[str, Callable[[RuleSet], Any]] = {
    "violates_policy": lambda rs: prompt_violates_policy(),
    "violated_rules": lambda rs: prompt_violated_rules(rs),
    "severity": lambda rs: prompt_enum("severity", Severity),
    "primary_category": lambda rs: prompt_enum("primary_category", PrimaryCategory),
    "evidence_spans": lambda rs: prompt_evidence_spans(),
    "suggested_action": lambda rs: prompt_enum("suggested_action", SuggestedAction),
    "confidence": lambda rs: prompt_confidence(),
    "reasoning": lambda rs: prompt_reasoning(),
}
JUDGMENT_FIELDS: tuple[str, ...] = tuple(PROMPTERS.keys())


def collect_judgment(rs: RuleSet) -> Judgment | None:
    """Collect 8 fields and validate; re-prompt only the failing fields on error.

    Returns None if the user gives up after RETRY_CAP retries.
    """
    d: dict[str, Any] = {f: PROMPTERS[f](rs) for f in JUDGMENT_FIELDS}
    retries = 0
    while True:
        try:
            return Judgment.model_validate(d)
        except ValidationError as err:
            retries += 1
            failing = sorted({str(e["loc"][0]) for e in err.errors() if e.get("loc")})
            print()
            print(f"validation error (attempt {retries}):")
            for e in err.errors():
                loc = ".".join(str(x) for x in e.get("loc", []))
                print(f"  - {loc}: {e['msg']}")
            print()
            if retries >= RETRY_CAP:
                choice = input("retry limit hit. [d]iscard / [k]eep trying: ").strip().lower()
                if choice != "k":
                    return None
                retries = 0
            print(f"re-prompting: {failing}")
            for f in failing:
                if f in PROMPTERS:
                    d[f] = PROMPTERS[f](rs)


# ───────────────────────────── Display ──────────────────────────────


def display_candidate(
    idx: int,
    total: int,
    state: SessionState,
    row: dict[str, Any],
    rs: RuleSet,
) -> None:
    elapsed = _elapsed_min(state.started_at)
    dev_marker = " [DEV]" if state.dev_mode else ""
    print()
    print(
        f"─── candidate {idx} of {total}  "
        f"(session {state.session_id}, {elapsed:.0f}m elapsed){dev_marker} ───"
    )
    print()
    print(f"text: {row['text']!r}")
    print()
    hf_id = row.get("id", "—")
    print(f"source: civil_comments  stream_idx={row.get('_stream_idx')}  hf_id={hf_id}")
    for col in TOX_COLUMNS:
        val = row.get(col)
        if val is None:
            print(f"  {col:<16} (missing)")
        else:
            print(f"  {col:<16} {float(val):.3f}")
    print()
    print(f"rules ({rs.slug}, regime={rs.regime.value}, {len(rs.rules)} rules):")
    for r in rs.rules:
        print(f"  {r.id}: {r.text}")
    print()


# ───────────────────────────── JSONL ────────────────────────────────


def append_jsonl(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
        f.flush()
        os.fsync(f.fileno())


def _content_regime(rs_regime: Regime) -> str:
    return "chat" if rs_regime is Regime.chat else "comment"


def build_jsonl_row(
    state: SessionState,
    rs: RuleSet,
    row: dict[str, Any],
    judgment: Judgment,
) -> dict[str, Any]:
    return {
        "session_id": state.session_id,
        "timestamp": _utc_now_iso(),
        "audited_by": "human",
        "rule_set_slug": rs.slug,
        "content": {
            "text": row["text"],
            "regime": _content_regime(rs.regime),
            "source": "civil_comments",
            "source_stream_idx": row.get("_stream_idx"),
            "source_hf_id": row.get("id"),
            "source_features": {
                col: (float(row[col]) if row.get(col) is not None else None) for col in TOX_COLUMNS
            },
        },
        "judgment": judgment.model_dump(mode="json"),
        "dev_mode": state.dev_mode,
    }


# ─────────────────────── Session lifecycle ──────────────────────────


def _start_fresh_or_block(
    latest: SessionState | None,
    rule_set_slug: str,
    n: int,
    seed: int,
    dev: bool,
) -> SessionState | None:
    if latest is not None and latest.ended_at is not None and not dev:
        remaining = cooldown_remaining_min(latest)
        if remaining > 0:
            print(
                f"cooldown active: {remaining:.1f}m remaining "
                f"(last session ended {latest.ended_at}).",
                file=sys.stderr,
            )
            return None
    s = SessionState.new(rule_set_slug=rule_set_slug, target_n=n, seed=seed, dev_mode=dev)
    save_session_state(s)
    print(f"started session {s.session_id} (target={s.target_n}, seed={s.seed})")
    return s


def _abandon_session(s: SessionState) -> None:
    s.ended_at = s.last_activity_at
    s.ended_reason = "abandoned"
    save_session_state(s)


def _end_session(state: SessionState, reason: str) -> int:
    state.ended_at = _utc_now_iso()
    state.ended_reason = reason
    state.last_activity_at = state.ended_at
    save_session_state(state)
    print()
    print(
        f"session {state.session_id} ended ({reason}): "
        f"{state.n_completed}/{state.target_n} judgments, {state.skips_used} skips"
    )
    return 0


def _run_loop(state: SessionState, rs: RuleSet, candidates: list[dict[str, Any]]) -> int:
    audit_path = _audit_file(state.dev_mode)
    total = state.target_n

    while state.n_completed < total:
        if state.cursor >= len(candidates):
            return _end_session(state, "candidates_exhausted")

        elapsed = _elapsed_min(state.started_at)
        if elapsed > SESSION_HARD_CAP_MIN:
            print()
            print(f"session cap reached after {SESSION_HARD_CAP_MIN}m — saving and exiting.")
            return _end_session(state, "time_cap")
        if elapsed > SESSION_WARN_MIN and not state.warned_25min:
            print()
            print(f"⚠️  ~{SESSION_HARD_CAP_MIN - SESSION_WARN_MIN}m left in this session.")
            state.warned_25min = True
            save_session_state(state)

        row = candidates[state.cursor]
        display_candidate(state.n_completed + 1, total, state, row, rs)

        action = input("[enter] judge   [s] skip-distressing   [q] save & quit\n> ").strip().lower()

        if action == "q":
            return _end_session(state, "user_quit")
        if action == "s":
            state.skips_used += 1
            state.cursor += 1
            state.last_activity_at = _utc_now_iso()
            save_session_state(state)
            if state.skips_used > MAX_SKIPS:
                print()
                print(f"{state.skips_used} skips this session — that's a sign to stop.")
                print("Take a break and come back later.")
                return _end_session(state, "skip_limit")
            continue
        if action not in ("", "j"):
            print("  unrecognized key; press enter to judge, s to skip, q to quit")
            continue

        judgment = collect_judgment(rs)
        state.cursor += 1
        state.last_activity_at = _utc_now_iso()
        if judgment is None:
            print("(judgment discarded)")
            save_session_state(state)
            continue

        jsonl_row = build_jsonl_row(state, rs, row, judgment)
        append_jsonl(audit_path, jsonl_row)
        state.n_completed += 1
        save_session_state(state)

    return _end_session(state, "target_reached")


# ─────────────────────────────── Main ───────────────────────────────


def _resolve_session(
    args: argparse.Namespace,
    rs: RuleSet,
    requested_seed: int,
) -> SessionState | None:
    """Pick up an active session, abandon one for a different rule set, or start fresh."""
    latest = find_latest_session(args.dev)

    if latest is not None and latest.ended_at is None:
        if latest.rule_set_slug == args.rule_set:
            ans = (
                input(
                    f"found partial session {latest.session_id}: "
                    f"{latest.n_completed}/{latest.target_n} done, "
                    f"cursor={latest.cursor}, skips={latest.skips_used}. resume? [y/n] "
                )
                .strip()
                .lower()
            )
            if ans in ("y", "yes"):
                latest.last_activity_at = _utc_now_iso()
                save_session_state(latest)
                print(f"resuming session {latest.session_id} (seed={latest.seed})")
                return latest
            _abandon_session(latest)
            return _start_fresh_or_block(latest, rs.slug, args.n, requested_seed, args.dev)

        ans = (
            input(
                f"partial session {latest.session_id} exists for rule_set="
                f"{latest.rule_set_slug!r} (current request: {args.rule_set!r}). "
                f"abandon it and start a new {args.rule_set!r} session? [y/n] "
            )
            .strip()
            .lower()
        )
        if ans not in ("y", "yes"):
            print("aborted: resolve the existing partial session first.", file=sys.stderr)
            return None
        _abandon_session(latest)
        return _start_fresh_or_block(latest, rs.slug, args.n, requested_seed, args.dev)

    return _start_fresh_or_block(latest, rs.slug, args.n, requested_seed, args.dev)


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    parser = argparse.ArgumentParser(description="Interactive single-session human audit.")
    parser.add_argument(
        "--rule-set",
        default="progamer_chat",
        help="Rule set slug under data/rule_sets/ (default: progamer_chat)",
    )
    parser.add_argument(
        "--n", type=int, default=15, help="Target judgments per session (default: 15)"
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="Sampling seed; default is time-based for fresh draws each run",
    )
    parser.add_argument(
        "--dev",
        action="store_true",
        help="Bypass cooldown and write to .dev paths. Do NOT use for real audits.",
    )
    args = parser.parse_args()

    if args.dev:
        print()
        print("⚠️  DEV MODE — cooldown bypassed; output goes to data/audit/week1.dev.jsonl")
        print("⚠️  Do NOT use --dev for real audit sessions.")
        print()

    try:
        rs = load_rule_set(args.rule_set)
    except (FileNotFoundError, yaml.YAMLError, ValidationError, ValueError) as e:
        print(f"FAIL: could not load rule set {args.rule_set!r}: {e}", file=sys.stderr)
        return 1

    requested_seed = args.seed if args.seed is not None else int(time.time())

    state = _resolve_session(args, rs, requested_seed)
    if state is None:
        return 1

    print()
    print(f"loading candidates from {DATASET_ID} (seed={state.seed})…")
    try:
        candidates = load_candidates(state.seed, rs.regime)
    except Exception as e:
        print(f"FAIL: dataset load failed: {e}", file=sys.stderr)
        return 1

    if not candidates:
        print("FAIL: no candidates passed length filter", file=sys.stderr)
        return 1

    remaining_target = state.target_n - state.n_completed
    if len(candidates) < remaining_target:
        logger.warning(
            "only %d candidates after filter; %d remaining of target %d",
            len(candidates),
            remaining_target,
            state.target_n,
        )

    print(f"got {len(candidates)} candidates after length filter")
    return _run_loop(state, rs, candidates)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\ninterrupted; partial session preserved for resume.", file=sys.stderr)
        sys.exit(130)
