"""Persistence interface for research sessions, plus an in-memory implementation.

The in-memory repository is used for local development and tests when Supabase is not configured.
It is NOT durable: all sessions are lost when the process restarts.
"""

from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Protocol

from app.models.agents import AGENT_ORDER, AgentExecution
from app.models.evidence import EvidenceRecord
from app.models.report import ResearchReport
from app.models.research import ResearchPlan, SessionStatus, SessionSummary
from app.models.session import SessionDetail


class SessionRepository(Protocol):
    durable: bool

    async def create_session(self, question: str, user_id: str | None, demo_mode: bool) -> str: ...
    async def set_status(self, session_id: str, status: SessionStatus) -> None: ...
    async def save_plan(self, session_id: str, plan: ResearchPlan) -> None: ...
    async def upsert_agent(self, session_id: str, execution: AgentExecution) -> None: ...
    async def save_evidence(self, session_id: str, records: list[EvidenceRecord]) -> None: ...
    async def complete(
        self, session_id: str, report: ResearchReport, profile: dict[str, Any], warnings: list[str]
    ) -> None: ...
    async def fail(
        self, session_id: str, error: str, profile: dict[str, Any] | None, warnings: list[str]
    ) -> None: ...
    async def get_session(self, session_id: str) -> tuple[SessionDetail, str | None] | None: ...
    async def get_evidence(self, session_id: str) -> list[EvidenceRecord]: ...
    async def list_sessions(self, user_id: str, limit: int = 50) -> list[SessionSummary]: ...
    async def fail_interrupted(self) -> int: ...


def ordered_agents(executions: dict[str, AgentExecution]) -> list[AgentExecution]:
    """All agents in pipeline order, defaulting to 'pending' for those not started yet."""
    return [executions.get(a.value) or AgentExecution(agent_name=a) for a in AGENT_ORDER]


ACTIVE_STATUSES = {
    SessionStatus.PENDING,
    SessionStatus.PLANNING,
    SessionStatus.RESEARCHING,
    SessionStatus.VALIDATING,
    SessionStatus.SYNTHESISING,
}


@dataclass
class _MemSession:
    id: str
    question: str
    user_id: str | None
    demo_mode: bool
    status: SessionStatus = SessionStatus.PENDING
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    completed_at: datetime | None = None
    plan: ResearchPlan | None = None
    agents: dict[str, AgentExecution] = field(default_factory=dict)
    evidence: list[EvidenceRecord] = field(default_factory=list)
    profile: dict[str, Any] | None = None
    warnings: list[str] = field(default_factory=list)
    error: str | None = None
    report: ResearchReport | None = None


class InMemorySessionRepository:
    durable = False

    def __init__(self) -> None:
        self._sessions: dict[str, _MemSession] = {}
        self._lock = asyncio.Lock()

    async def create_session(self, question: str, user_id: str | None, demo_mode: bool) -> str:
        sid = str(uuid.uuid4())
        async with self._lock:
            self._sessions[sid] = _MemSession(id=sid, question=question, user_id=user_id, demo_mode=demo_mode)
        return sid

    async def set_status(self, session_id: str, status: SessionStatus) -> None:
        self._sessions[session_id].status = status

    async def save_plan(self, session_id: str, plan: ResearchPlan) -> None:
        self._sessions[session_id].plan = plan

    async def upsert_agent(self, session_id: str, execution: AgentExecution) -> None:
        self._sessions[session_id].agents[execution.agent_name.value] = execution.model_copy(deep=True)

    async def save_evidence(self, session_id: str, records: list[EvidenceRecord]) -> None:
        self._sessions[session_id].evidence = list(records)

    async def complete(self, session_id, report, profile, warnings) -> None:  # type: ignore[no-untyped-def]
        s = self._sessions[session_id]
        s.report, s.profile, s.warnings = report, profile, list(warnings)
        s.status, s.completed_at = SessionStatus.COMPLETED, datetime.now(UTC)

    async def fail(self, session_id, error, profile, warnings) -> None:  # type: ignore[no-untyped-def]
        s = self._sessions[session_id]
        s.error, s.profile, s.warnings = error, profile, list(warnings)
        s.status, s.completed_at = SessionStatus.FAILED, datetime.now(UTC)

    async def get_session(self, session_id: str) -> tuple[SessionDetail, str | None] | None:
        s = self._sessions.get(session_id)
        if s is None:
            return None
        detail = SessionDetail(
            session_id=s.id,
            research_question=s.question,
            status=s.status,
            demo_mode=s.demo_mode,
            created_at=s.created_at,
            completed_at=s.completed_at,
            research_plan=s.plan,
            agents=ordered_agents(s.agents),
            evidence_profile=s.profile,
            warnings=s.warnings,
            error_message=s.error,
            report=s.report,
        )
        return detail, s.user_id

    async def get_evidence(self, session_id: str) -> list[EvidenceRecord]:
        s = self._sessions.get(session_id)
        return list(s.evidence) if s else []

    async def list_sessions(self, user_id: str, limit: int = 50) -> list[SessionSummary]:
        own = sorted(
            (s for s in self._sessions.values() if s.user_id == user_id),
            key=lambda s: s.created_at,
            reverse=True,
        )[:limit]
        return [
            SessionSummary(
                session_id=s.id,
                research_question=s.question,
                status=s.status,
                demo_mode=s.demo_mode,
                created_at=s.created_at,
                completed_at=s.completed_at,
            )
            for s in own
        ]

    async def fail_interrupted(self) -> int:
        return 0  # nothing survives a restart in memory
