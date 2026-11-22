"""Research request, plan and session models."""

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field, field_validator

from app.models.evidence import SourceName

MIN_QUESTION_LENGTH = 20
MAX_QUESTION_LENGTH = 2000


class SessionStatus(StrEnum):
    PENDING = "pending"
    PLANNING = "planning"
    RESEARCHING = "researching"
    VALIDATING = "validating"
    SYNTHESISING = "synthesising"
    COMPLETED = "completed"
    FAILED = "failed"


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


class ResearchPlan(BaseModel):
    """Structured interpretation of the user's question produced by the Research Planner agent.

    Lists contain *topics mentioned or implied by the question*, not scientific claims.
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
