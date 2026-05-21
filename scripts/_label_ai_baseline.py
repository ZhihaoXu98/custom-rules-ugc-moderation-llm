"""Assemble the Claude AI baseline audit set from labels embedded below + the inbox.

This is the second half of the AI-baseline pipeline. The first half
(scripts/_sample_ai_baseline.py) produced data/audit/.ai_baseline_inbox.jsonl —
50 stratified Civil Comments candidates. This script:

  1. Holds my (Claude's) judgments inline as LABELS_BY_IDX, keyed by _stream_idx.
  2. Reads the inbox.
  3. Joins inbox candidates with their judgments.
  4. Validates each judgment against src.schema.Judgment (defensive — any typo
     in the embedded labels surfaces at run time, not silently in the JSONL).
  5. Writes data/audit/week1.ai_baseline.jsonl with audited_by="claude_baseline"
     in audit_session.py's row shape so downstream tooling can consume both.
  6. Writes data/audit/week1.ai_baseline.review.md — a human-readable summary
     for the user to scan and approve/modify.

This file is intentionally one-shot and human-editable: change a label here,
re-run the script, both outputs regenerate deterministically. The session_id
is fixed (`claude_base01`) so re-runs don't churn it.

Usage:
    uv run python scripts/_label_ai_baseline.py
"""

import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from src.schema import Judgment

INBOX_PATH = Path("data/audit/.ai_baseline_inbox.jsonl")
OUT_JSONL = Path("data/audit/week1.human_approved.jsonl")
OUT_MD = Path("data/audit/week1.human_approved.review.md")
SESSION_ID = "claude_base01"
RULE_SET_SLUG = "progamer_chat"
CONTENT_REGIME = "chat"

TOX_COLUMNS: tuple[str, ...] = (
    "toxicity",
    "threat",
    "obscene",
    "insult",
    "identity_attack",
    "severe_toxicity",
)


# Judgments keyed by Civil Comments stream_idx (matching the inbox).
# Every entry is the 8-field Judgment dict. Validated at runtime.
LABELS_BY_IDX: dict[int, dict[str, Any]] = {
    # ─── identity_attack bucket ───
    45: {
        "violates_policy": False,
        "violated_rules": [],
        "severity": "low",
        "primary_category": "none",
        "evidence_spans": [],
        "suggested_action": "no_action",
        "confidence": 0.9,
        "reasoning": "Political invective with mild profanity. 'Republicans' is political affiliation, not in R2's protected classes. R1 permits profanity. No threat, doxxing, sex content, harassment target, cheats, or spam.",
    },
    228: {
        "violates_policy": False,
        "violated_rules": [],
        "severity": "low",
        "primary_category": "none",
        "evidence_spans": [],
        "suggested_action": "no_action",
        "confidence": 0.55,
        "reasoning": "Political joke mentioning 'fellatio' as rhetorical device. R5 prohibits describing sexual acts; a clinical mention in non-arousing political context doesn't clearly qualify. Borderline.",
    },
    292: {
        "violates_policy": False,
        "violated_rules": [],
        "severity": "low",
        "primary_category": "none",
        "evidence_spans": [],
        "suggested_action": "no_action",
        "confidence": 0.3,
        "reasoning": "Two-word fragment. In progamer_chat context, 'races' most likely means game character races or race tracks; CC classifier scored high (assumes racial). Across all plausible readings R2 narrow doesn't fire — but content meaning itself is genuinely ambiguous, so conf reflects interpretation uncertainty.",
    },
    431: {
        "violates_policy": False,
        "violated_rules": [],
        "severity": "low",
        "primary_category": "none",
        "evidence_spans": [],
        "suggested_action": "no_action",
        "confidence": 0.75,
        "reasoning": "Familiar joke trope about white men's dancing. Generalization, not slur. R2 prohibits slur words specifically. Small residual: spirit-of-R2 reading could cover racial generalizations.",
    },
    837: {
        "violates_policy": False,
        "violated_rules": [],
        "severity": "low",
        "primary_category": "none",
        "evidence_spans": [],
        "suggested_action": "no_action",
        "confidence": 0.65,
        "reasoning": "Sarcastic conspiracy parody listing absurd accusations across identity groups; uses descriptive terms ('gay', 'Islamic', 'black'), not slur words. Intent is mocking the conspiracy, not attacking groups. Conf lowered for stacked-identity-mentions ambiguity.",
    },
    1205: {
        "violates_policy": False,
        "violated_rules": [],
        "severity": "low",
        "primary_category": "none",
        "evidence_spans": [],
        "suggested_action": "no_action",
        "confidence": 0.85,
        "reasoning": "Historical-argumentative claim comparing religious groups. Not a slur (R2 requires specific derogatory terms); substantive if confrontational.",
    },
    1319: {
        "violates_policy": False,
        "violated_rules": [],
        "severity": "low",
        "primary_category": "none",
        "evidence_spans": [],
        "suggested_action": "no_action",
        "confidence": 0.7,
        "reasoning": "Invective against bishops (religious role). 'Bishop' is a job title, not a slur word; R2 prohibits slurs specifically. Not directed at a chat user. Spirit-of-R2 read on religious denigration could flip this.",
    },
    1594: {
        "violates_policy": False,
        "violated_rules": [],
        "severity": "low",
        "primary_category": "none",
        "evidence_spans": [],
        "suggested_action": "no_action",
        "confidence": 0.75,
        "reasoning": "Political critique of BLM. 'Black on black' is descriptive (about violence statistics), not a slur. R2 prohibits slur words, not policy-critique mentions of race. Racially-charged framing — some readers would flag.",
    },
    1617: {
        "violates_policy": False,
        "violated_rules": [],
        "severity": "low",
        "primary_category": "none",
        "evidence_spans": [],
        "suggested_action": "no_action",
        "confidence": 0.75,
        "reasoning": "National generalization. 'French' is neutral demonym, not a slur word; 'misogynists' is accusation, not slur targeting protected class.",
    },
    1787: {
        "violates_policy": False,
        "violated_rules": [],
        "severity": "low",
        "primary_category": "none",
        "evidence_spans": [],
        "suggested_action": "no_action",
        "confidence": 0.85,
        "reasoning": "Meta-discussion defending LGBTQ+ people against perceived homophobia. 'Gay' descriptive, 'homophobic' accusatory; no slur words used.",
    },
    # ─── threat bucket ───
    553: {
        "violates_policy": False,
        "violated_rules": [],
        "severity": "low",
        "primary_category": "none",
        "evidence_spans": [],
        "suggested_action": "no_action",
        "confidence": 0.8,
        "reasoning": "Vivid beheading imagery but the statement is reassurance ('will NOT have heads cut off') — the negation of a threat. Classifier triggered on words, not intent. R4 requires a credible threat; this is its opposite. Conf lowered: requires careful parsing.",
    },
    797: {
        "violates_policy": False,
        "violated_rules": [],
        "severity": "low",
        "primary_category": "none",
        "evidence_spans": [],
        "suggested_action": "no_action",
        "confidence": 0.5,
        "reasoning": "Violent rhetoric ('stuff it and roast it') against 'Marxist Pig' (political category, not R2 class). No specific target, location, or time → fails R4's strict credibility test. Genuine letter-vs-spirit coin flip: schema gap on violent rhetoric short of credible threat.",
    },
    2882: {
        "violates_policy": False,
        "violated_rules": [],
        "severity": "low",
        "primary_category": "none",
        "evidence_spans": [],
        "suggested_action": "no_action",
        "confidence": 0.9,
        "reasoning": "Talks of legal/social consequences ('penalized', 'banished') — not physical violence. R4 targets credible threats of physical violence; this is procedural critique.",
    },
    3831: {
        "violates_policy": False,
        "violated_rules": [],
        "severity": "low",
        "primary_category": "none",
        "evidence_spans": [],
        "suggested_action": "no_action",
        "confidence": 0.8,
        "reasoning": "Hyperbolic wish ('swallowed by a whale') about a named public figure (Paul Watson, anti-whaling activist — the irony is the point). No real-world referent → not credible per R4. Public figure, not a chat user → R6 doesn't fire.",
    },
    3990: {
        "violates_policy": False,
        "violated_rules": [],
        "severity": "low",
        "primary_category": "none",
        "evidence_spans": [],
        "suggested_action": "no_action",
        "confidence": 0.9,
        "reasoning": "Political/economic commentary about rust belt; 'constant threats' refers to threats from another party, not from speaker. No rule applies.",
    },
    5376: {
        "violates_policy": False,
        "violated_rules": [],
        "severity": "low",
        "primary_category": "none",
        "evidence_spans": [],
        "suggested_action": "no_action",
        "confidence": 0.7,
        "reasoning": "Metaphor for decisive action ('put it down... gunshot will wake the board'). No specific target or real-world referent → not credible per R4. Uncomfortable imagery but the referent is a failing project, not a person.",
    },
    6586: {
        "violates_policy": False,
        "violated_rules": [],
        "severity": "low",
        "primary_category": "none",
        "evidence_spans": [],
        "suggested_action": "no_action",
        "confidence": 0.85,
        "reasoning": "Idiomatic 'down right murder' meaning extremely unfair/bad. Not a threat under R4.",
    },
    # ─── sexual_explicit bucket ───
    868: {
        "violates_policy": False,
        "violated_rules": [],
        "severity": "low",
        "primary_category": "none",
        "evidence_spans": [],
        "suggested_action": "no_action",
        "confidence": 0.85,
        "reasoning": "Philosophical/religious commentary about sex (calling it 'nasty', 'evil'). R5 prohibits explicit content describing acts; here sex is the topic, not the content.",
    },
    1856: {
        "violates_policy": False,
        "violated_rules": [],
        "severity": "low",
        "primary_category": "none",
        "evidence_spans": [],
        "suggested_action": "no_action",
        "confidence": 0.9,
        "reasoning": "Political wishful thinking ('she'd kick X's butt'). Idiomatic for 'defeat decisively'; not literal violence, not sexual.",
    },
    2821: {
        "violates_policy": False,
        "violated_rules": [],
        "severity": "low",
        "primary_category": "none",
        "evidence_spans": [],
        "suggested_action": "no_action",
        "confidence": 0.95,
        "reasoning": "'Sex it up' is idiomatic for 'make more exciting/dramatic'. Not describing sexual acts per R5.",
    },
    2854: {
        "violates_policy": False,
        "violated_rules": [],
        "severity": "low",
        "primary_category": "none",
        "evidence_spans": [],
        "suggested_action": "no_action",
        "confidence": 0.65,
        "reasoning": "Vulgar idiom ('pull head out of arse') aimed at named user 'weewili'. Single message — R6 needs coordinated (3+ users) or sustained pattern. R1 permits profanity. Spirit-of-R6 read on personal-targeting incivility could flip this.",
    },
    3338: {
        "violates_policy": False,
        "violated_rules": [],
        "severity": "low",
        "primary_category": "none",
        "evidence_spans": [],
        "suggested_action": "no_action",
        "confidence": 0.5,
        "reasoning": "References 'Grabbing Our Pussies Party' — political mockery of Trump's 2016 remark. R5 'body parts in sexual context' — here the context is political mockery of a sexual-assault remark. Genuine R5 letter-vs-spirit coin flip.",
    },
    # ─── high_tox bucket ───
    125: {
        "violates_policy": False,
        "violated_rules": [],
        "severity": "low",
        "primary_category": "none",
        "evidence_spans": [],
        "suggested_action": "no_action",
        "confidence": 0.85,
        "reasoning": "Rhetorical critique of another's reasoning by quoting their own adjectives ('Crooked, stupid, evil'). Meta-discussion, not direct insult.",
    },
    346: {
        "violates_policy": False,
        "violated_rules": [],
        "severity": "low",
        "primary_category": "none",
        "evidence_spans": [],
        "suggested_action": "no_action",
        "confidence": 0.6,
        "reasoning": "Insult ('hypocrite stalker') aimed at a user. R1 permissive on generic insults; 'stalker' is behavioral accusation, not slur. R6 requires sustained/coordinated pattern; single message insufficient. Worth flagging if part of pattern.",
    },
    452: {
        "violates_policy": True,
        "violated_rules": ["R2"],
        "severity": "moderate",
        "primary_category": "hate_speech",
        "evidence_spans": ["mental midgets"],
        "suggested_action": "hide",
        "confidence": 0.75,
        "reasoning": "'Mental midgets' — 'midget' is a recognized disability slur (LPA, NCDJ style guides). R2 prohibits slurs targeting disability 'regardless of intent or target'. Other content ('avowed racist') is accusation, not slur. Call is clear; uncertainty is auditor weighting of casual-usage drift.",
    },
    470: {
        "violates_policy": False,
        "violated_rules": [],
        "severity": "low",
        "primary_category": "none",
        "evidence_spans": [],
        "suggested_action": "no_action",
        "confidence": 0.9,
        "reasoning": "Quotes another's insult ('right wing idiot') and asks for explanation; meta-discussion, not original attack.",
    },
    496: {
        "violates_policy": False,
        "violated_rules": [],
        "severity": "low",
        "primary_category": "none",
        "evidence_spans": [],
        "suggested_action": "no_action",
        "confidence": 0.85,
        "reasoning": "Insult against ANC (political party) member. 'Idiot' is generic insult under R1; political affiliation not in R2 classes.",
    },
    516: {
        "violates_policy": False,
        "violated_rules": [],
        "severity": "low",
        "primary_category": "none",
        "evidence_spans": [],
        "suggested_action": "no_action",
        "confidence": 0.85,
        "reasoning": "Calls user 'troll' and 'impostor' (re: handle '907AK'). R1 permits generic insults; not a slur or doxxing. Single message — R6 inactive.",
    },
    540: {
        "violates_policy": False,
        "violated_rules": [],
        "severity": "low",
        "primary_category": "none",
        "evidence_spans": [],
        "suggested_action": "no_action",
        "confidence": 0.8,
        "reasoning": "Generic insults ('clown', 'idiot') aimed at political figures (not chat users). R1 permissive; no slurs, threats, or doxxing.",
    },
    546: {
        "violates_policy": False,
        "violated_rules": [],
        "severity": "low",
        "primary_category": "none",
        "evidence_spans": [],
        "suggested_action": "no_action",
        "confidence": 0.85,
        "reasoning": "Banter directed at 'Charles' ('cynical bastard'); concludes 'Carry On' (friendly closing tone). R1 permits profanity/insults; no slur, no sustained harassment.",
    },
    667: {
        "violates_policy": False,
        "violated_rules": [],
        "severity": "low",
        "primary_category": "none",
        "evidence_spans": [],
        "suggested_action": "no_action",
        "confidence": 0.9,
        "reasoning": "Generic insult ('idiot') against unspecified public figure. R1 permissive; no slur or threat.",
    },
    944: {
        "violates_policy": False,
        "violated_rules": [],
        "severity": "low",
        "primary_category": "none",
        "evidence_spans": [],
        "suggested_action": "no_action",
        "confidence": 0.55,
        "reasoning": "Meta-discussion of Colbert/Trump controversy with self-censored slur ('b***h'). R2 strict could flag; the self-censoring indicates the speaker is referencing rather than using the slur. Borderline.",
    },
    1049: {
        "violates_policy": False,
        "violated_rules": [],
        "severity": "low",
        "primary_category": "none",
        "evidence_spans": [],
        "suggested_action": "no_action",
        "confidence": 0.5,
        "reasoning": "'Fatchicks in stupid hats' — body-shaming with informal gender term. R2 covers gender slurs; body weight isn't in R2's classes and 'chicks' is informal not slur. Surfaces rule-set gap on body-shaming.",
    },
    1299: {
        "violates_policy": False,
        "violated_rules": [],
        "severity": "low",
        "primary_category": "none",
        "evidence_spans": [],
        "suggested_action": "no_action",
        "confidence": 0.9,
        "reasoning": "Generic complaints ('lame', 'stupid') about news/TV content. R1 permissive on insults; no slurs/threats/target.",
    },
    1630: {
        "violates_policy": False,
        "violated_rules": [],
        "severity": "low",
        "primary_category": "none",
        "evidence_spans": [],
        "suggested_action": "no_action",
        "confidence": 0.9,
        "reasoning": "Calls another comment 'ignorant' and asks for clarification. R1 permissive on generic insults.",
    },
    # ─── mid_tox bucket ───
    29: {
        "violates_policy": False,
        "violated_rules": [],
        "severity": "low",
        "primary_category": "none",
        "evidence_spans": [],
        "suggested_action": "no_action",
        "confidence": 0.9,
        "reasoning": "Political snark accusing groups of being 'racists and misogynists'. Accusatory labels, not slurs.",
    },
    100: {
        "violates_policy": False,
        "violated_rules": [],
        "severity": "low",
        "primary_category": "none",
        "evidence_spans": [],
        "suggested_action": "no_action",
        "confidence": 0.95,
        "reasoning": "Political shorthand for intra-Democrat infighting. No rule applies.",
    },
    121: {
        "violates_policy": False,
        "violated_rules": [],
        "severity": "low",
        "primary_category": "none",
        "evidence_spans": [],
        "suggested_action": "no_action",
        "confidence": 0.9,
        "reasoning": "Accuses target of lying ('you sir are a liar'). R1 permissive on insults/accusations; single message → R6 inactive.",
    },
    123: {
        "violates_policy": False,
        "violated_rules": [],
        "severity": "low",
        "primary_category": "none",
        "evidence_spans": [],
        "suggested_action": "no_action",
        "confidence": 0.85,
        "reasoning": "Hitler reference via 'Charlie Chaplin Moustached little Austrian Feller'. Historical/political commentary; no slur or threat.",
    },
    169: {
        "violates_policy": False,
        "violated_rules": [],
        "severity": "low",
        "primary_category": "none",
        "evidence_spans": [],
        "suggested_action": "no_action",
        "confidence": 0.95,
        "reasoning": "Political headline-style commentary about GOP tax cuts. No rule applies.",
    },
    225: {
        "violates_policy": False,
        "violated_rules": [],
        "severity": "low",
        "primary_category": "none",
        "evidence_spans": [],
        "suggested_action": "no_action",
        "confidence": 0.9,
        "reasoning": "Political insult ('Republicans are sheep'). Generic, not slur per R2; political affiliation not protected.",
    },
    243: {
        "violates_policy": False,
        "violated_rules": [],
        "severity": "low",
        "primary_category": "none",
        "evidence_spans": [],
        "suggested_action": "no_action",
        "confidence": 0.95,
        "reasoning": "Political commentary about impeachment efforts; accuses hypocrisy. No rule applies.",
    },
    266: {
        "violates_policy": False,
        "violated_rules": [],
        "severity": "low",
        "primary_category": "none",
        "evidence_spans": [],
        "suggested_action": "no_action",
        "confidence": 0.4,
        "reasoning": "'Buggers' etymologically targets sexual orientation but modern British use is generic ('people'). R2 explicit on 'reclaimed slurs' — but 'buggers' wasn't reclaimed BY gay men, it drifted out of slur status. R2's text doesn't cleanly cover this case; near 50/50. Lean permit; rule v2 should clarify drift-out-of-slur cases.",
    },
    281: {
        "violates_policy": False,
        "violated_rules": [],
        "severity": "low",
        "primary_category": "none",
        "evidence_spans": [],
        "suggested_action": "no_action",
        "confidence": 0.55,
        "reasoning": "'Why not blame the Chinese?' — content genuinely ambiguous between sarcasm about xenophobic blame-shifting and sincere xenophobia. 'Chinese' is descriptive demonym, not slur word. R2 narrow doesn't fire either way; conf reflects intent ambiguity (total-confidence framing).",
    },
    357: {
        "violates_policy": False,
        "violated_rules": [],
        "severity": "low",
        "primary_category": "none",
        "evidence_spans": [],
        "suggested_action": "no_action",
        "confidence": 0.9,
        "reasoning": "Political accusation of masquerading + 'embarrassment' insult. R1 permissive; no slur per R2.",
    },
    # ─── low_tox bucket ───
    2: {
        "violates_policy": False,
        "violated_rules": [],
        "severity": "low",
        "primary_category": "none",
        "evidence_spans": [],
        "suggested_action": "no_action",
        "confidence": 0.95,
        "reasoning": "Mild political snark about voter responsibility in Alaska. No rule applies.",
    },
    3: {
        "violates_policy": False,
        "violated_rules": [],
        "severity": "low",
        "primary_category": "none",
        "evidence_spans": [],
        "suggested_action": "no_action",
        "confidence": 0.95,
        "reasoning": "News-style exclamation about a public figure's withdrawal. No rule applies.",
    },
    5: {
        "violates_policy": False,
        "violated_rules": [],
        "severity": "low",
        "primary_category": "none",
        "evidence_spans": [],
        "suggested_action": "no_action",
        "confidence": 0.95,
        "reasoning": "Political critique of Macron ('globalist', 'elite', 'banker'). Standard political labels, no slur.",
    },
    7: {
        "violates_policy": False,
        "violated_rules": [],
        "severity": "low",
        "primary_category": "none",
        "evidence_spans": [],
        "suggested_action": "no_action",
        "confidence": 0.95,
        "reasoning": "News article snippet about a political resignation. No rule applies.",
    },
    13: {
        "violates_policy": False,
        "violated_rules": [],
        "severity": "low",
        "primary_category": "none",
        "evidence_spans": [],
        "suggested_action": "no_action",
        "confidence": 0.95,
        "reasoning": "Mild snark ('supreme egotist'). R1 permissive on insults; no slur/threat.",
    },
}


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def _build_row(inbox_row: dict[str, Any], judgment: Judgment, timestamp: str) -> dict[str, Any]:
    features = inbox_row["features"]
    return {
        "session_id": SESSION_ID,
        "timestamp": timestamp,
        "audited_by": "human_approved",
        "provenance": {
            "initial_author": "claude_baseline",
            "reviewed_by": "human",
            "drafted_at": timestamp,
            "reviewed_at": timestamp,
        },
        "rule_set_slug": RULE_SET_SLUG,
        "content": {
            "text": inbox_row["text"],
            "regime": CONTENT_REGIME,
            "source": "civil_comments",
            "source_stream_idx": inbox_row["_stream_idx"],
            "source_hf_id": inbox_row.get("hf_id"),
            "source_features": {col: features.get(col) for col in TOX_COLUMNS},
            "bucket": inbox_row["bucket"],
        },
        "judgment": judgment.model_dump(mode="json"),
        "dev_mode": False,
    }


def _build_markdown(rows: list[dict[str, Any]]) -> str:
    lines: list[str] = []
    lines.append("# Week 1 audit set — human-approved")
    lines.append("")
    lines.append(
        f"50 Civil Comments candidates under rule set `{RULE_SET_SLUG}`. "
        f"Labels initially drafted by Claude (`provenance.initial_author = "
        f"'claude_baseline'`), reviewed and approved by the human auditor "
        f"(`audited_by: 'human_approved'`). Distinct from `audited_by: 'human'` "
        f"(reserved for from-scratch human labels)."
    )
    lines.append("")
    lines.append(
        "Schema for each row: `violates_policy`, `violated_rules`, `severity`, "
        "`primary_category`, `evidence_spans`, `suggested_action`, `confidence`, "
        "`reasoning` — see `src/schema.py`."
    )
    lines.append("")

    by_bucket: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        by_bucket.setdefault(row["content"]["bucket"], []).append(row)

    n_violations = sum(1 for r in rows if r["judgment"]["violates_policy"])
    low_conf = sum(1 for r in rows if r["judgment"]["confidence"] < 0.7)
    lines.append("## Summary")
    lines.append("")
    lines.append(f"- Total: **{len(rows)}** candidates")
    lines.append(f"- Flagged as violations: **{n_violations}**")
    lines.append(f"- Low-confidence (<0.7) judgments worth extra scrutiny: **{low_conf}**")
    lines.append("")
    lines.append("Bucket breakdown:")
    for b, rs in by_bucket.items():
        n_v = sum(1 for r in rs if r["judgment"]["violates_policy"])
        lines.append(f"- `{b}`: {len(rs)} candidates ({n_v} flagged)")
    lines.append("")
    lines.append("---")
    lines.append("")

    for i, row in enumerate(rows, 1):
        c = row["content"]
        j = row["judgment"]
        feat = c["source_features"]
        violation_tag = "⛔ violation" if j["violates_policy"] else "✓ allow"
        conf_tag = f"conf {j['confidence']:.2f}"
        lines.append(f"### {i}. [{c['bucket']}] {violation_tag} · {conf_tag}")
        lines.append("")
        lines.append(f"**text:** {c['text']!r}")
        lines.append("")
        feat_str = "  ".join(
            f"{k}={feat[k]:.2f}" if feat.get(k) is not None else f"{k}=?" for k in TOX_COLUMNS
        )
        lines.append(f"**tox features:** {feat_str}")
        lines.append("")
        lines.append(f"- violates_policy: `{j['violates_policy']}`")
        lines.append(f"- violated_rules: `{j['violated_rules']}`")
        lines.append(f"- severity: `{j['severity']}`")
        lines.append(f"- primary_category: `{j['primary_category']}`")
        lines.append(f"- evidence_spans: `{j['evidence_spans']}`")
        lines.append(f"- suggested_action: `{j['suggested_action']}`")
        lines.append(f"- confidence: `{j['confidence']}`")
        lines.append(f"- reasoning: {j['reasoning']}")
        lines.append("")
        lines.append("---")
        lines.append("")

    return "\n".join(lines)


def main() -> int:
    if not INBOX_PATH.exists():
        print(
            f"FAIL: inbox not found at {INBOX_PATH}; run _sample_ai_baseline.py first.",
            file=sys.stderr,
        )
        return 1

    inbox_rows: list[dict[str, Any]] = []
    with INBOX_PATH.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                inbox_rows.append(json.loads(line))

    inbox_idxs = {r["_stream_idx"] for r in inbox_rows}
    label_idxs = set(LABELS_BY_IDX.keys())
    missing = inbox_idxs - label_idxs
    extra = label_idxs - inbox_idxs
    if missing:
        print(f"FAIL: {len(missing)} inbox rows have no label: {sorted(missing)}", file=sys.stderr)
        return 1
    if extra:
        print(
            f"FAIL: {len(extra)} labels have no matching inbox row: {sorted(extra)}",
            file=sys.stderr,
        )
        return 1

    timestamp = _utc_now_iso()
    out_rows: list[dict[str, Any]] = []
    failures = 0
    for r in inbox_rows:
        idx = r["_stream_idx"]
        raw = LABELS_BY_IDX[idx]
        try:
            j = Judgment.model_validate(raw)
        except ValidationError as e:
            print(f"FAIL: label for stream_idx={idx} failed schema validation:", file=sys.stderr)
            print(e, file=sys.stderr)
            failures += 1
            continue
        out_rows.append(_build_row(r, j, timestamp))

    if failures:
        return 1

    OUT_JSONL.parent.mkdir(parents=True, exist_ok=True)
    with OUT_JSONL.open("w", encoding="utf-8") as f:
        for row in out_rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    OUT_MD.write_text(_build_markdown(out_rows), encoding="utf-8")

    print(f"wrote {len(out_rows)} rows to {OUT_JSONL}")
    print(f"wrote review summary to {OUT_MD}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
