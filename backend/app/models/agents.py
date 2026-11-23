"""Agent execution tracking shared by the workflow, persistence layer and API."""

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class AgentName(StrEnum):
    PLANNER = "research_planner"
    LITERATURE = "literature_agent"
    CLINICAL = "clinical_agent"
    TARGETS = "target_agent"
    COMPOUNDS = "compound_agent"
    VALIDATION = "evidence_validation"
    SYNTHESIS = "research_synthesis"
    VERIFICATION = "claim_verification"


AGENT_ORDER: list[AgentName] = list(AgentName)

AGENT_LABELS: dict[AgentName, str] = {
    AgentName.PLANNER: "Research Planner",
    AgentName.LITERATURE: "Literature Agent",
    AgentName.CLINICAL: "Clinical Intelligence Agent",
    AgentName.TARGETS: "Biological Target Agent",
    AgentName.COMPOUNDS: "Compound Agent",
    AgentName.VALIDATION: "Evidence Validation Agent",
    AgentName.SYNTHESIS: "Research Synthesis Agent",
    AgentName.VERIFICATION: "Claim Verification Agent",
}


class ExecutionStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    PARTIAL = "partial"  # finished, but at least one of its sources failed
    FAILED = "failed"
    SKIPPED = "skipped"


class SourceOutcome(BaseModel):
    """What one query against one source returned. Kept for the audit trail."""

    source: str
    ok: bool
    record_count: int = 0
    error: str | None = None
    query: str | None = None
    total_available: int | None = None  # matching records the source reports, when it reports a count
    requested: int | None = None  # the cap applied from the protocol
    pages: int | None = None


class AgentExecution(BaseModel):
    agent_name: AgentName
    status: ExecutionStatus = ExecutionStatus.PENDING
    started_at: datetime | None = None
    completed_at: datetime | None = None
    duration_ms: int | None = None
    record_count: int | None = None
    message: str | None = None
    error_message: str | None = None
    sources: list[SourceOutcome] = Field(default_factory=list)
