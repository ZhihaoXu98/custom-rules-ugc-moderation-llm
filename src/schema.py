"""Pydantic v2 contracts for the moderation LLM.

Pinned per CLAUDE.md — changes here require retraining and re-eval.
"""

from datetime import date
from enum import StrEnum
from typing import Annotated, Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)

RuleId = Annotated[str, StringConstraints(pattern=r"^R\d{1,3}$")]
ShortText = Annotated[str, StringConstraints(min_length=1, max_length=300)]


class Severity(StrEnum):
    low = "low"
    moderate = "moderate"
    high = "high"
    critical = "critical"


class PrimaryCategory(StrEnum):
    harassment = "harassment"
    hate_speech = "hate_speech"
    sexual = "sexual"
    violence = "violence"
    spam = "spam"
    self_harm = "self_harm"
    other = "other"
    none = "none"


class SuggestedAction(StrEnum):
    no_action = "no_action"
    warn = "warn"
    hide = "hide"
    remove = "remove"
    escalate = "escalate"
    ban = "ban"


class Regime(StrEnum):
    chat = "chat"
    comment = "comment"
    hybrid = "hybrid"


class ContentRegime(StrEnum):
    chat = "chat"
    comment = "comment"


class Judgment(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    violates_policy: bool
    violated_rules: list[RuleId] = Field(default_factory=list, max_length=10)
    severity: Severity
    primary_category: PrimaryCategory
    evidence_spans: list[ShortText] = Field(default_factory=list, max_length=5)
    suggested_action: SuggestedAction
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning: Annotated[str, StringConstraints(min_length=1, max_length=400)]

    @field_validator("violated_rules")
    @classmethod
    def _rules_unique(cls, v: list[str]) -> list[str]:
        if len(v) != len(set(v)):
            raise ValueError("violated_rules must be unique")
        return v


class Rule(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: RuleId
    text: ShortText


class RuleSet(BaseModel):
    model_config = ConfigDict(extra="forbid")

    slug: Annotated[str, StringConstraints(pattern=r"^[a-z0-9_]+$", max_length=64)]
    name: Annotated[str, StringConstraints(min_length=1, max_length=120)]
    regime: Regime
    description: Annotated[str, StringConstraints(min_length=20, max_length=500)]
    rules: list[Rule] = Field(min_length=3, max_length=20)
    version: int = 1
    created: date

    @field_validator("rules")
    @classmethod
    def _rule_ids_unique(cls, v: list[Rule]) -> list[Rule]:
        ids = [r.id for r in v]
        if len(ids) != len(set(ids)):
            raise ValueError("rule ids must be unique within a rule set")
        return v


class Content(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: Annotated[str, StringConstraints(min_length=1, max_length=4000)]
    regime: ContentRegime
    article_title: ShortText | None = None
    language: str = "en"

    @model_validator(mode="after")
    def _title_matches_regime(self) -> Self:
        if self.regime is ContentRegime.comment and self.article_title is None:
            raise ValueError("article_title is required when regime='comment'")
        if self.regime is ContentRegime.chat and self.article_title is not None:
            raise ValueError("article_title must be omitted when regime='chat'")
        return self
