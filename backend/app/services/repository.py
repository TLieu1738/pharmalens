"""Persistence interface for research sessions and their jobs, plus an in-memory implementation.

A research session doubles as a durable job record: `status` says what work is due (pending → plan it,
queued → execute it), and a worker claims the job by taking a time-limited lease, which it renews while it
works. If the worker dies, the lease expires and `recover_stale` re-queues the job (bounded attempts).

The in-memory repository is used for local development and tests when Supabase is not configured.
It is NOT durable: all sessions are lost when the process restarts.
"""

from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol

from app.models.agents import AGENT_ORDER, AgentExecution
from app.models.evidence import EvidenceRecord
from app.models.report import ResearchReport
from app.models.research import (
    RUNNING_STATUSES,
    TERMINAL_STATUSES,
    ResearchPlan,
    SessionStatus,
    SessionSummary,
)
from app.models.session import SessionDetail


@dataclass
class ClaimedJob:
    session_id: str
    question: str
    phase: str  # "plan" | "execute"
    plan: ResearchPlan | None
    attempts: int


class SessionRepository(Protocol):
    durable: bool

    async def create_session(
        self, question: str, user_id: str | None, demo_mode: bool, plan: ResearchPlan | None = None
    ) -> str: ...
    # -- jobs -------------------------------------------------------------------------------------------
    async def claim_job(self, worker_id: str, lease_seconds: int) -> ClaimedJob | None: ...
    async def renew_lease(self, session_id: str, worker_id: str, lease_seconds: int) -> bool: ...
    async def recover_stale(self, max_attempts: int) -> tuple[int, int]: ...
    async def finish_planning(self, session_id: str) -> None: ...
    async def update_plan(self, session_id: str, plan: ResearchPlan) -> bool: ...
    async def approve(self, session_id: str, plan: ResearchPlan) -> bool: ...
    async def cancel(self, session_id: str) -> bool: ...
    async def get_status(self, session_id: str) -> SessionStatus | None: ...
    async def reset_run(self, session_id: str) -> None: ...
    async def save_audit(self, session_id: str, audit: dict[str, Any]) -> None: ...
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


def ordered_agents(executions: dict[str, AgentExecution]) -> list[AgentExecution]:
    """All agents in pipeline order, defaulting to 'pending' for those not started yet."""
    return [executions.get(a.value) or AgentExecution(agent_name=a) for a in AGENT_ORDER]


ACTIVE_STATUSES = {
    SessionStatus.PENDING,
    SessionStatus.PLANNING,
    SessionStatus.QUEUED,
    SessionStatus.RESEARCHING,
    SessionStatus.VALIDATING,
    SessionStatus.SYNTHESISING,
}
INTERRUPTED_MESSAGE = "Interrupted repeatedly while running; stopped after {n} attempts."


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
    attempts: int = 0
    worker_id: str | None = None
    lease_until: datetime | None = None
    approved_at: datetime | None = None
    audit: dict[str, Any] | None = None


class InMemorySessionRepository:
    durable = False

    def __init__(self) -> None:
        self._sessions: dict[str, _MemSession] = {}
        self._lock = asyncio.Lock()

    async def create_session(
        self, question: str, user_id: str | None, demo_mode: bool, plan: ResearchPlan | None = None
    ) -> str:
        sid = str(uuid.uuid4())
        async with self._lock:
            self._sessions[sid] = _MemSession(
                id=sid,
                question=question,
                user_id=user_id,
                demo_mode=demo_mode,
                plan=plan,
                status=SessionStatus.AWAITING_APPROVAL if plan else SessionStatus.PENDING,
            )
        return sid

    # -- jobs -------------------------------------------------------------------------------------------
    async def claim_job(self, worker_id: str, lease_seconds: int) -> ClaimedJob | None:
        now = datetime.now(UTC)
        async with self._lock:
            due = sorted(
                (
                    s
                    for s in self._sessions.values()
                    if s.status in (SessionStatus.PENDING, SessionStatus.QUEUED)
                    and (s.lease_until is None or s.lease_until < now)
                ),
                key=lambda s: s.created_at,
            )
            if not due:
                return None
            s = due[0]
            phase = "plan" if s.status == SessionStatus.PENDING else "execute"
            s.status = SessionStatus.PLANNING if phase == "plan" else SessionStatus.RESEARCHING
            s.attempts += 1
            s.worker_id, s.lease_until = worker_id, now + timedelta(seconds=lease_seconds)
            return ClaimedJob(s.id, s.question, phase, s.plan, s.attempts)

    async def renew_lease(self, session_id: str, worker_id: str, lease_seconds: int) -> bool:
        s = self._sessions.get(session_id)
        if s is None or s.worker_id != worker_id or s.status in TERMINAL_STATUSES:
            return False
        s.lease_until = datetime.now(UTC) + timedelta(seconds=lease_seconds)
        return True

    async def recover_stale(self, max_attempts: int) -> tuple[int, int]:
        now = datetime.now(UTC)
        requeued = failed = 0
        async with self._lock:
            for s in self._sessions.values():
                if s.status not in RUNNING_STATUSES or (s.lease_until and s.lease_until > now):
                    continue
                s.worker_id = s.lease_until = None
                if s.attempts >= max_attempts:
                    s.status, s.error = SessionStatus.FAILED, INTERRUPTED_MESSAGE.format(n=s.attempts)
                    s.completed_at = now
                    failed += 1
                else:
                    s.status = SessionStatus.QUEUED if s.approved_at else SessionStatus.PENDING
                    requeued += 1
        return requeued, failed

    async def finish_planning(self, session_id: str) -> None:
        s = self._sessions[session_id]
        if s.status == SessionStatus.PLANNING:
            s.status, s.worker_id, s.lease_until, s.attempts = SessionStatus.AWAITING_APPROVAL, None, None, 0

    async def update_plan(self, session_id: str, plan: ResearchPlan) -> bool:
        s = self._sessions.get(session_id)
        if s is None or s.status != SessionStatus.AWAITING_APPROVAL:
            return False
        s.plan = plan
        return True

    async def approve(self, session_id: str, plan: ResearchPlan) -> bool:
        s = self._sessions.get(session_id)
        if s is None or s.status != SessionStatus.AWAITING_APPROVAL:
            return False
        s.plan, s.status, s.approved_at, s.attempts = plan, SessionStatus.QUEUED, datetime.now(UTC), 0
        return True

    async def cancel(self, session_id: str) -> bool:
        s = self._sessions.get(session_id)
        if s is None or s.status in TERMINAL_STATUSES:
            return False
        s.status, s.completed_at, s.worker_id, s.lease_until = (
            SessionStatus.CANCELLED,
            datetime.now(UTC),
            None,
            None,
        )
        return True

    async def get_status(self, session_id: str) -> SessionStatus | None:
        s = self._sessions.get(session_id)
        return s.status if s else None

    async def reset_run(self, session_id: str) -> None:
        s = self._sessions[session_id]
        s.evidence, s.report, s.profile, s.error = [], None, None, None
        s.agents = {k: v for k, v in s.agents.items() if k == "research_planner"}

    async def save_audit(self, session_id: str, audit: dict[str, Any]) -> None:
        self._sessions[session_id].audit = audit

    async def set_status(self, session_id: str, status: SessionStatus) -> None:
        s = self._sessions[session_id]
        if s.status not in TERMINAL_STATUSES:  # progress never overrides cancelled / finished
            s.status = status

    async def save_plan(self, session_id: str, plan: ResearchPlan) -> None:
        self._sessions[session_id].plan = plan

    async def upsert_agent(self, session_id: str, execution: AgentExecution) -> None:
        self._sessions[session_id].agents[execution.agent_name.value] = execution.model_copy(deep=True)

    async def save_evidence(self, session_id: str, records: list[EvidenceRecord]) -> None:
        self._sessions[session_id].evidence = list(records)

    async def complete(self, session_id, report, profile, warnings) -> None:  # type: ignore[no-untyped-def]
        s = self._sessions[session_id]
        if s.status == SessionStatus.CANCELLED:
            return
        s.report, s.profile, s.warnings = report, profile, list(warnings)
        s.status, s.completed_at = SessionStatus.COMPLETED, datetime.now(UTC)
        s.worker_id = s.lease_until = None

    async def fail(self, session_id, error, profile, warnings) -> None:  # type: ignore[no-untyped-def]
        s = self._sessions[session_id]
        if s.status == SessionStatus.CANCELLED:
            return
        s.error, s.profile, s.warnings = error, profile, list(warnings)
        s.status, s.completed_at = SessionStatus.FAILED, datetime.now(UTC)
        s.worker_id = s.lease_until = None

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
            protocol_approved_at=s.approved_at,
            attempts=s.attempts,
            run_audit=s.audit,
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
                attempts=s.attempts,
            )
            for s in own
        ]

    # Test hook: simulate a worker that died mid-run (its lease lapsed).
    def expire_lease(self, session_id: str) -> None:
        self._sessions[session_id].lease_until = datetime.now(UTC) - timedelta(seconds=1)
