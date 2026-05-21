"""Tests for src/schema.py.

Each test carries a 'predicted:' comment (pass/fail) authored before
running pytest, per the Week 1 Day 2 plan.
"""

from datetime import date
from typing import Any

import pytest
from pydantic import ValidationError

from src.schema import (
    Content,
    ContentRegime,
    Judgment,
    PrimaryCategory,
    Regime,
    Rule,
    RuleSet,
    Severity,
    SuggestedAction,
)


def _valid_judgment_kwargs() -> dict[str, Any]:
    return dict(
        violates_policy=True,
        violated_rules=["R1", "R23"],
        severity=Severity.moderate,
        primary_category=PrimaryCategory.harassment,
        evidence_spans=["go away loser"],
        suggested_action=SuggestedAction.hide,
        confidence=0.87,
        reasoning="Targeted insult of an individual; matches R1 (no personal attacks).",
    )


# predicted: pass — every field is within constraints
def test_valid_judgment_passes() -> None:
    j = Judgment(**_valid_judgment_kwargs())
    assert j.violates_policy is True
    assert j.violated_rules == ["R1", "R23"]
    assert j.severity is Severity.moderate


# predicted: fail — R1234 has 4 digits; pattern is ^R\d{1,3}$
def test_bad_rule_id_format_rejected() -> None:
    kwargs = _valid_judgment_kwargs()
    kwargs["violated_rules"] = ["R1234"]
    with pytest.raises(ValidationError):
        Judgment(**kwargs)


# predicted: fail — extra="forbid" rejects unknown fields
def test_extra_field_rejected() -> None:
    kwargs = _valid_judgment_kwargs()
    kwargs["bogus"] = "x"
    with pytest.raises(ValidationError):
        Judgment(**kwargs)


# predicted: fail — confidence has le=1.0
def test_confidence_over_one_rejected() -> None:
    kwargs = _valid_judgment_kwargs()
    kwargs["confidence"] = 1.5
    with pytest.raises(ValidationError):
        Judgment(**kwargs)


# predicted: fail — frozen=True raises ValidationError on attribute set
def test_judgment_is_frozen() -> None:
    j = Judgment(**_valid_judgment_kwargs())
    with pytest.raises(ValidationError):
        j.confidence = 0.5  # type: ignore[misc]


# predicted: pass — RuleSet(regime=comment) + Content(regime=comment, article_title set)
def test_ruleset_comment_with_content_article_title() -> None:
    rs = RuleSet(
        slug="default_news_comments",
        name="Default news comment policy",
        regime=Regime.comment,
        description="Baseline rules for moderating news article comment sections.",
        rules=[
            Rule(id="R1", text="No personal attacks on other commenters."),
            Rule(id="R2", text="No hate speech against protected classes."),
            Rule(id="R3", text="No spam, advertisements, or off-topic links."),
        ],
        created=date(2026, 5, 20),
    )
    c = Content(
        text="This article is dumb and so is the author.",
        regime=ContentRegime.comment,
        article_title="City Council Approves Budget",
    )
    assert rs.regime is Regime.comment
    assert c.article_title == "City Council Approves Budget"
