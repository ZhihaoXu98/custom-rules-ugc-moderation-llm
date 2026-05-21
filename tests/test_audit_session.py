"""Unit tests for scripts/audit_session.py pure helpers."""

import time
from datetime import UTC, datetime, timedelta

import pytest

from scripts.audit_session import (
    SessionState,
    _content_regime,
    _passes_length,
    build_jsonl_row,
    collect_judgment,
    cooldown_remaining_min,
    find_latest_session,
    is_resumable,
    load_session_state,
    prompt_violated_rules,
    save_session_state,
)
from src.schema import Judgment, Regime, RuleSet

TEST_RULE_SET = RuleSet.model_validate(
    {
        "slug": "test_set",
        "name": "Test Rules",
        "regime": "chat",
        "description": "A test rule set with three rules for unit testing purposes.",
        "rules": [
            {"id": "R1", "text": "first rule about banned content"},
            {"id": "R2", "text": "second rule about other content"},
            {"id": "R3", "text": "third rule about more content"},
        ],
        "version": 1,
        "created": "2026-05-21",
    }
)


def _iso(dt: datetime) -> str:
    return dt.isoformat(timespec="seconds").replace("+00:00", "Z")


# ─── length filter ───


def test_passes_length_chat_within_range():
    assert _passes_length("a" * 100, Regime.chat) is True
    assert _passes_length("a" * 5, Regime.chat) is True
    assert _passes_length("a" * 149, Regime.chat) is True


def test_passes_length_chat_rejects_too_long():
    assert _passes_length("a" * 150, Regime.chat) is False
    assert _passes_length("a" * 200, Regime.chat) is False


def test_passes_length_chat_rejects_too_short():
    assert _passes_length("a" * 4, Regime.chat) is False
    assert _passes_length("", Regime.chat) is False


def test_passes_length_comment_within_range():
    assert _passes_length("a" * 200, Regime.comment) is True
    assert _passes_length("a" * 1000, Regime.comment) is True
    assert _passes_length("a" * 5, Regime.comment) is True


def test_passes_length_comment_rejects_outside_range():
    assert _passes_length("a" * 1001, Regime.comment) is False
    assert _passes_length("a" * 4, Regime.comment) is False


# ─── session state ───


def test_session_state_roundtrip(tmp_path, monkeypatch):
    import scripts.audit_session as mod

    monkeypatch.setattr(mod, "DEV_SESSIONS_DIR", tmp_path)
    s = SessionState.new(rule_set_slug="progamer_chat", target_n=15, seed=42, dev_mode=True)
    save_session_state(s)
    loaded = load_session_state(tmp_path / f"{s.session_id}.json")
    assert loaded == s


def test_find_latest_session_empty(tmp_path, monkeypatch):
    import scripts.audit_session as mod

    monkeypatch.setattr(mod, "DEV_SESSIONS_DIR", tmp_path)
    assert find_latest_session(dev=True) is None


def test_find_latest_session_picks_most_recent(tmp_path, monkeypatch):
    import scripts.audit_session as mod

    monkeypatch.setattr(mod, "DEV_SESSIONS_DIR", tmp_path)
    s1 = SessionState.new(rule_set_slug="r", target_n=10, seed=1, dev_mode=True)
    save_session_state(s1)
    time.sleep(0.02)
    s2 = SessionState.new(rule_set_slug="r", target_n=10, seed=2, dev_mode=True)
    save_session_state(s2)
    found = find_latest_session(dev=True)
    assert found is not None
    assert found.session_id == s2.session_id


def test_find_latest_session_skips_unreadable(tmp_path, monkeypatch):
    import scripts.audit_session as mod

    monkeypatch.setattr(mod, "DEV_SESSIONS_DIR", tmp_path)
    s1 = SessionState.new(rule_set_slug="r", target_n=10, seed=1, dev_mode=True)
    save_session_state(s1)
    time.sleep(0.02)
    # write a junk file with a newer mtime
    (tmp_path / "junk.json").write_text("{not json")
    found = find_latest_session(dev=True)
    assert found is not None
    assert found.session_id == s1.session_id


# ─── cooldown / resume ───


def _ended_session(*, ended_at: str, target_n: int = 10, n_completed: int = 10) -> SessionState:
    return SessionState(
        session_id="x",
        rule_set_slug="r",
        target_n=target_n,
        n_completed=n_completed,
        cursor=n_completed,
        skips_used=0,
        seed=1,
        started_at=ended_at,
        last_activity_at=ended_at,
        ended_at=ended_at,
        ended_reason="target_reached",
        warned_25min=False,
        dev_mode=False,
    )


def test_cooldown_remaining_recent_session():
    ended = _iso(datetime.now(UTC) - timedelta(minutes=30))
    remaining = cooldown_remaining_min(_ended_session(ended_at=ended))
    # 90 - 30 = 60, allow for a few seconds of slop
    assert 59.0 < remaining < 61.0


def test_cooldown_expired():
    ended = _iso(datetime.now(UTC) - timedelta(minutes=120))
    assert cooldown_remaining_min(_ended_session(ended_at=ended)) == 0.0


def test_cooldown_for_active_session_is_zero():
    s = SessionState.new(rule_set_slug="r", target_n=10, seed=1, dev_mode=False)
    assert cooldown_remaining_min(s) == 0.0


def test_is_resumable_active_same_slug():
    s = SessionState.new(rule_set_slug="r", target_n=10, seed=1, dev_mode=False)
    s.n_completed = 3
    assert is_resumable(s, "r") is True


def test_is_resumable_different_slug():
    s = SessionState.new(rule_set_slug="r", target_n=10, seed=1, dev_mode=False)
    s.n_completed = 3
    assert is_resumable(s, "other") is False


def test_is_resumable_target_reached():
    s = SessionState.new(rule_set_slug="r", target_n=10, seed=1, dev_mode=False)
    s.n_completed = 10
    assert is_resumable(s, "r") is False


def test_is_resumable_already_ended():
    s = SessionState.new(rule_set_slug="r", target_n=10, seed=1, dev_mode=False)
    s.n_completed = 3
    s.ended_at = _iso(datetime.now(UTC))
    assert is_resumable(s, "r") is False


# ─── prompts ───


def test_prompt_violated_rules_accepts_valid(monkeypatch):
    monkeypatch.setattr("builtins.input", lambda *a, **k: "R1,R2")
    assert prompt_violated_rules(TEST_RULE_SET) == ["R1", "R2"]


def test_prompt_violated_rules_empty(monkeypatch):
    monkeypatch.setattr("builtins.input", lambda *a, **k: "")
    assert prompt_violated_rules(TEST_RULE_SET) == []


def test_prompt_violated_rules_rejects_unknown(monkeypatch):
    inputs = iter(["R99", "R1"])
    monkeypatch.setattr("builtins.input", lambda *a, **k: next(inputs))
    assert prompt_violated_rules(TEST_RULE_SET) == ["R1"]


def test_prompt_violated_rules_rejects_duplicates(monkeypatch):
    inputs = iter(["R1,R1", "R1,R2"])
    monkeypatch.setattr("builtins.input", lambda *a, **k: next(inputs))
    assert prompt_violated_rules(TEST_RULE_SET) == ["R1", "R2"]


def test_collect_judgment_happy_path(monkeypatch):
    inputs = iter(
        [
            "y",  # violates_policy
            "R1,R2",  # violated_rules
            "high",  # severity
            "harassment",  # primary_category
            "the bad part",  # evidence_spans #1
            "",  # evidence_spans done
            "remove",  # suggested_action
            "0.9",  # confidence
            "this is a clear violation of R1",  # reasoning
        ]
    )
    monkeypatch.setattr("builtins.input", lambda *a, **k: next(inputs))
    j = collect_judgment(TEST_RULE_SET)
    assert j is not None
    assert j.violates_policy is True
    assert j.violated_rules == ["R1", "R2"]
    assert j.severity.value == "high"
    assert j.primary_category.value == "harassment"
    assert j.evidence_spans == ["the bad part"]
    assert j.suggested_action.value == "remove"
    assert j.confidence == pytest.approx(0.9)
    assert "violation" in j.reasoning


def test_collect_judgment_numeric_enum_choice(monkeypatch):
    # severity option 3 is "high" (low=1, moderate=2, high=3, critical=4)
    inputs = iter(
        [
            "n",  # violates_policy
            "",  # violated_rules
            "1",  # severity → low (option 1)
            "8",  # primary_category → "none" (option 8)
            "",  # evidence_spans done
            "1",  # suggested_action → no_action (option 1)
            "0.4",  # confidence
            "clean content; no policy implications",  # reasoning
        ]
    )
    monkeypatch.setattr("builtins.input", lambda *a, **k: next(inputs))
    j = collect_judgment(TEST_RULE_SET)
    assert j is not None
    assert j.violates_policy is False
    assert j.severity.value == "low"
    assert j.primary_category.value == "none"
    assert j.suggested_action.value == "no_action"


# ─── content / JSONL row ───


def test_content_regime_mapping():
    assert _content_regime(Regime.chat) == "chat"
    assert _content_regime(Regime.comment) == "comment"
    assert _content_regime(Regime.hybrid) == "comment"


def _sample_judgment() -> Judgment:
    return Judgment.model_validate(
        {
            "violates_policy": True,
            "violated_rules": ["R1"],
            "severity": "high",
            "primary_category": "harassment",
            "evidence_spans": ["bad"],
            "suggested_action": "remove",
            "confidence": 0.9,
            "reasoning": "clear violation",
        }
    )


def test_build_jsonl_row_full():
    state = SessionState.new(rule_set_slug="test_set", target_n=10, seed=1, dev_mode=False)
    row = {
        "text": "test content",
        "_stream_idx": 42,
        "id": "abc",
        "toxicity": 0.5,
        "threat": 0.1,
        "obscene": 0.2,
        "insult": 0.3,
        "identity_attack": 0.0,
        "severe_toxicity": 0.05,
    }
    out = build_jsonl_row(state, TEST_RULE_SET, row, _sample_judgment())
    assert out["session_id"] == state.session_id
    assert out["audited_by"] == "human"
    assert out["rule_set_slug"] == "test_set"
    assert out["content"]["text"] == "test content"
    assert out["content"]["regime"] == "chat"
    assert out["content"]["source"] == "civil_comments"
    assert out["content"]["source_stream_idx"] == 42
    assert out["content"]["source_hf_id"] == "abc"
    assert out["content"]["source_features"]["toxicity"] == pytest.approx(0.5)
    assert out["content"]["source_features"]["severe_toxicity"] == pytest.approx(0.05)
    assert out["judgment"]["violates_policy"] is True
    assert out["judgment"]["severity"] == "high"
    assert out["dev_mode"] is False


def test_build_jsonl_row_missing_features():
    state = SessionState.new(rule_set_slug="test_set", target_n=10, seed=1, dev_mode=True)
    row = {"text": "x", "_stream_idx": 0, "id": None}
    j = Judgment.model_validate(
        {
            "violates_policy": False,
            "violated_rules": [],
            "severity": "low",
            "primary_category": "none",
            "evidence_spans": [],
            "suggested_action": "no_action",
            "confidence": 0.5,
            "reasoning": "clean",
        }
    )
    out = build_jsonl_row(state, TEST_RULE_SET, row, j)
    for col in ("toxicity", "threat", "obscene", "insult", "identity_attack", "severe_toxicity"):
        assert out["content"]["source_features"][col] is None
    assert out["dev_mode"] is True
