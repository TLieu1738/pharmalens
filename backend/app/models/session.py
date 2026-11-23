"""Session read models returned by the API."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.models.agents import AgentExecution
from app.models.report import ResearchReport
from app.models.research import ResearchPlan, SessionStatus


class SessionDetail(BaseModel):
    session_id: str
    research_question: str
    status: SessionStatus
    demo_mode: bool = False
    created_at: datetime
    completed_at: datetime | None = None
    research_plan: ResearchPlan | None = None
    agents: list[AgentExecution] = Field(default_factory=list)
    evidence_profile: dict[str, Any] | None = None
    warnings: list[str] = Field(default_factory=list)
    error_message: str | None = None
    report: ResearchReport | None = None
    is_owner: bool = False
    protocol_approved_at: datetime | None = None
    attempts: int = 0
    run_audit: dict[str, Any] | None = None
