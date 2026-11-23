"""Research request, plan and session models."""

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field, field_validator, model_validator

from app.models.evidence import SourceName

MIN_QUESTION_LENGTH = 20
MAX_QUESTION_LENGTH = 2000


class SessionStatus(StrEnum):
    """Lifecycle of a research job.

    pending → planning → awaiting_approval → (user approves) queued → researching → validating →
    synthesising → completed. Terminal states: completed, failed, cancelled. A job re-queued after an
    interruption goes back to pending/queued with `attempts` > 1 (shown as "retrying").
    """

    PENDING = "pending"  # queued for planning
    PLANNING = "planning"
    AWAITING_APPROVAL = "awaiting_approval"
    QUEUED = "queued"  # protocol approved, queued for execution
    RESEARCHING = "researching"
    VALIDATING = "validating"
    SYNTHESISING = "synthesising"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


TERMINAL_STATUSES = {SessionStatus.COMPLETED, SessionStatus.FAILED, SessionStatus.CANCELLED}
RUNNING_STATUSES = {
    SessionStatus.PLANNING,
    SessionStatus.RESEARCHING,
    SessionStatus.VALIDATING,
    SessionStatus.SYNTHESISING,
}


class ResearchRequest(BaseModel):
    research_question: str = Field(min_length=MIN_QUESTION_LENGTH, max_length=MAX_QUESTION_LENGTH)

    @field_validator("research_question", mode="before")
    @classmethod
    def _normalise(cls, value: object) -> object:
        if isinstance(value, str):
            # Collapse whitespace and strip control characters
            value = " ".join("".join(ch for ch in value if ch.isprintable() or ch.isspace()).split())
        return value

    @field_validator("research_question")
    @classmethod
    def _looks_like_a_question(cls, value: str) -> str:
        words = [w for w in value.split() if sum(c.isalpha() for c in w) >= 2]
        if len(words) < 3:
            raise ValueError("research question must contain at least three words")
        if len(set(value.lower())) < 8:
            raise ValueError("research question does not look like natural language")
        return value


DEFAULT_RESULTS_PER_SOURCE = 20
MAX_RESULTS_PER_SOURCE = 100
_TERM_MAX = 200


def _clean_terms(values: list[str]) -> list[str]:
    seen: dict[str, str] = {}
    for v in values:
        v = " ".join(str(v).split())[:_TERM_MAX]
        if v and v.lower() not in seen:
            seen[v.lower()] = v
    return list(seen.values())


class ResearchPlan(BaseModel):
    """The research protocol: drafted by the Research Planner agent, then reviewed and approved by the user.

    Lists contain *topics mentioned or implied by the question*, not scientific claims. Fields below
    `rationale` were added for the protocol-approval workflow and have defaults so older stored plans load.
    """

    disease_area: str | None = Field(default=None, description="Primary disease / research area, if any.")
    biological_targets: list[str] = Field(default_factory=list, max_length=10)
    target_gene_symbols: list[str] = Field(default_factory=list, max_length=10)
    compounds: list[str] = Field(default_factory=list, max_length=10)
    concepts: list[str] = Field(default_factory=list, max_length=10)
    objectives: list[str] = Field(default_factory=list, max_length=10)
    literature_query: str = Field(description="Boolean-friendly keyword query for PubMed / Europe PMC.")
    clinical_condition: str | None = Field(default=None, description="Condition term for ClinicalTrials.gov.")
    clinical_intervention_terms: list[str] = Field(default_factory=list, max_length=5)
    sources: list[SourceName] = Field(default_factory=lambda: list(SourceName))
    rationale: str = Field(default="", description="Brief explanation of the plan, for display.")

    # -- protocol fields --------------------------------------------------------------------------------
    objective: str = Field(default="", max_length=1000, description="One-sentence research objective.")
    key_questions: list[str] = Field(default_factory=list, max_length=8)
    additional_literature_queries: list[str] = Field(
        default_factory=list,
        max_length=3,
        description="Extra PubMed / Europe PMC queries run alongside the main one.",
    )
    inclusion_criteria: list[str] = Field(default_factory=list, max_length=10)
    exclusion_criteria: list[str] = Field(default_factory=list, max_length=10)
    date_from: int | None = Field(
        default=None, ge=1900, le=2100, description="Earliest publication / trial start year."
    )
    date_to: int | None = Field(default=None, ge=1900, le=2100)
    include_preprints: bool = True
    max_results_per_source: int = Field(default=DEFAULT_RESULTS_PER_SOURCE, ge=5, le=MAX_RESULTS_PER_SOURCE)
    intended_outputs: list[str] = Field(default_factory=list, max_length=10)
    known_limitations: list[str] = Field(default_factory=list, max_length=10)

    @field_validator(
        "biological_targets",
        "target_gene_symbols",
        "compounds",
        "concepts",
        "objectives",
        "clinical_intervention_terms",
        "key_questions",
        "additional_literature_queries",
        "inclusion_criteria",
        "exclusion_criteria",
        "intended_outputs",
        "known_limitations",
        mode="after",
    )
    @classmethod
    def _dedupe_terms(cls, values: list[str]) -> list[str]:
        return _clean_terms(values)

    @field_validator("literature_query")
    @classmethod
    def _query_not_blank(cls, value: str) -> str:
        value = " ".join(value.split())
        if not value:
            raise ValueError("literature query cannot be empty")
        return value[:500]

    @field_validator("sources")
    @classmethod
    def _at_least_one_source(cls, value: list[SourceName]) -> list[SourceName]:
        value = list(dict.fromkeys(value))
        if not value:
            raise ValueError("select at least one data source")
        return value

    @model_validator(mode="after")
    def _date_order(self) -> "ResearchPlan":
        if self.date_from and self.date_to and self.date_from > self.date_to:
            raise ValueError("date_from must not be after date_to")
        return self

    @property
    def literature_queries(self) -> list[str]:
        return _clean_terms([self.literature_query, *self.additional_literature_queries])


class ResearchCreatedResponse(BaseModel):
    session_id: str
    status: SessionStatus


class SessionSummary(BaseModel):
    session_id: str
    research_question: str
    status: SessionStatus
    demo_mode: bool = False
    created_at: datetime
    completed_at: datetime | None = None
    attempts: int = 0
