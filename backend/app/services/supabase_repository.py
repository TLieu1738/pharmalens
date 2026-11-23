"""Supabase (PostgreSQL via PostgREST) implementation of SessionRepository.

Uses the service-role key, which bypasses RLS — so this module is server-side only, and every read path
in the API enforces ownership before returning data (see `api/routes/sessions.py`).
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx

from app.config import Settings
from app.models.agents import AgentExecution
from app.models.evidence import EvidenceRecord
from app.models.report import ResearchReport, ensure_publishable
from app.models.research import (
    RUNNING_STATUSES,
    TERMINAL_STATUSES,
    ResearchPlan,
    SessionStatus,
    SessionSummary,
)
from app.models.session import SessionDetail
from app.services.repository import INTERRUPTED_MESSAGE, ClaimedJob, ordered_agents

logger = logging.getLogger(__name__)

EVIDENCE_BATCH = 200


class SupabaseError(Exception):
    pass


def service_headers(key: str) -> dict[str, str]:
    """Headers for server-side REST calls.

    New-style secret keys (`sb_secret_...`) are not JWTs and go only in `apikey`; legacy service_role
    JWTs are also sent as the bearer token.
    """
    headers = {"apikey": key, "Content-Type": "application/json"}
    if not key.startswith("sb_"):
        headers["Authorization"] = f"Bearer {key}"
    return headers


class SupabaseSessionRepository:
    durable = True

    def __init__(self, settings: Settings, client: httpx.AsyncClient | None = None) -> None:
        if not (settings.supabase_url and settings.supabase_service_role_key):
            raise SupabaseError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are required")
        key = settings.supabase_service_role_key.get_secret_value()
        self._client = client or httpx.AsyncClient(
            base_url=f"{settings.supabase_url.rstrip('/')}/rest/v1",
            headers=service_headers(key),
            timeout=15,
        )

    async def _req(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, str] | None = None,
        json: Any = None,
        prefer: str | None = None,
    ) -> Any:
        headers = {"Prefer": prefer} if prefer else {}
        resp = await self._client.request(method, path, params=params, json=json, headers=headers)
        if resp.status_code >= 400:
            # Log the PostgREST message server-side only.
            logger.error(
                "supabase_error method=%s path=%s status=%s body=%s",
                method,
                path,
                resp.status_code,
                resp.text[:500],
            )
            raise SupabaseError(f"database request failed ({resp.status_code})")
        return resp.json() if resp.content else None

    async def _update_session(self, session_id: str, fields: dict[str, Any]) -> None:
        await self._req("PATCH", "/research_sessions", params={"id": f"eq.{session_id}"}, json=fields)

    async def _patch_where(self, filters: dict[str, str], fields: dict[str, Any]) -> list[dict[str, Any]]:
        """Conditional update: only rows matching `filters` change. Returns the rows that did."""
        rows = await self._req(
            "PATCH", "/research_sessions", params=filters, prefer="return=representation", json=fields
        )
        return rows or []

    # -- writes -------------------------------------------------------------------------------------------
    async def create_session(
        self, question: str, user_id: str | None, demo_mode: bool, plan: ResearchPlan | None = None
    ) -> str:
        rows = await self._req(
            "POST",
            "/research_sessions",
            prefer="return=representation",
            json={
                "research_question": question,
                "user_id": user_id,
                "demo_mode": demo_mode,
                "status": "awaiting_approval" if plan else "pending",
                "research_plan": plan.model_dump(mode="json") if plan else None,
            },
        )
        return rows[0]["id"]

    # -- jobs -------------------------------------------------------------------------------------------
    async def claim_job(self, worker_id: str, lease_seconds: int) -> ClaimedJob | None:
        now = _iso(datetime.now(UTC))
        candidates = await self._req(
            "GET",
            "/research_sessions",
            params={
                "status": "in.(pending,queued)",
                "or": f'(lease_expires_at.is.null,lease_expires_at.lt."{now}")',
                "order": "created_at.asc",
                "limit": "5",
                "select": "id,status,attempts,research_question,research_plan",
            },
        )
        for row in candidates or []:
            phase = "plan" if row["status"] == "pending" else "execute"
            attempts = int(row.get("attempts") or 0)
            claimed = await self._patch_where(
                {
                    "id": f"eq.{row['id']}",
                    "status": f"eq.{row['status']}",
                    "attempts": f"eq.{attempts}",
                },
                {
                    "status": "planning" if phase == "plan" else "researching",
                    "attempts": attempts + 1,
                    "worker_id": worker_id,
                    "lease_expires_at": _iso(datetime.now(UTC) + timedelta(seconds=lease_seconds)),
                },
            )
            if claimed:  # another worker may have won the race; the guards make this atomic
                plan = row.get("research_plan")
                return ClaimedJob(
                    session_id=row["id"],
                    question=row["research_question"],
                    phase=phase,
                    plan=ResearchPlan.model_validate(plan) if plan else None,
                    attempts=attempts + 1,
                )
        return None

    async def renew_lease(self, session_id: str, worker_id: str, lease_seconds: int) -> bool:
        rows = await self._patch_where(
            {"id": f"eq.{session_id}", "worker_id": f"eq.{worker_id}", "status": f"not.in.({_terminal()})"},
            {"lease_expires_at": _iso(datetime.now(UTC) + timedelta(seconds=lease_seconds))},
        )
        return bool(rows)

    async def recover_stale(self, max_attempts: int) -> tuple[int, int]:
        now = _iso(datetime.now(UTC))
        running = ",".join(s.value for s in RUNNING_STATUSES)
        stale = await self._req(
            "GET",
            "/research_sessions",
            params={
                "status": f"in.({running})",
                "or": f'(lease_expires_at.is.null,lease_expires_at.lt."{now}")',
                "select": "id,status,attempts,protocol_approved_at",
            },
        )
        requeued = failed = 0
        for row in stale or []:
            attempts = int(row.get("attempts") or 0)
            guard = {"id": f"eq.{row['id']}", "status": f"eq.{row['status']}", "attempts": f"eq.{attempts}"}
            if attempts >= max_attempts:
                fields = {
                    "status": "failed",
                    "error_message": INTERRUPTED_MESSAGE.format(n=attempts),
                    "completed_at": now,
                    "worker_id": None,
                    "lease_expires_at": None,
                }
            else:
                fields = {
                    "status": "queued" if row.get("protocol_approved_at") else "pending",
                    "worker_id": None,
                    "lease_expires_at": None,
                }
            if await self._patch_where(guard, fields):
                if fields["status"] == "failed":
                    failed += 1
                else:
                    requeued += 1
        return requeued, failed

    async def finish_planning(self, session_id: str) -> None:
        await self._patch_where(
            {"id": f"eq.{session_id}", "status": "eq.planning"},
            {"status": "awaiting_approval", "worker_id": None, "lease_expires_at": None, "attempts": 0},
        )

    async def update_plan(self, session_id: str, plan: ResearchPlan) -> bool:
        rows = await self._patch_where(
            {"id": f"eq.{session_id}", "status": "eq.awaiting_approval"},
            {"research_plan": plan.model_dump(mode="json")},
        )
        return bool(rows)

    async def approve(self, session_id: str, plan: ResearchPlan) -> bool:
        rows = await self._patch_where(
            {"id": f"eq.{session_id}", "status": "eq.awaiting_approval"},
            {
                "research_plan": plan.model_dump(mode="json"),
                "status": "queued",
                "protocol_approved_at": _iso(datetime.now(UTC)),
                "attempts": 0,
            },
        )
        return bool(rows)

    async def cancel(self, session_id: str) -> bool:
        rows = await self._patch_where(
            {"id": f"eq.{session_id}", "status": f"not.in.({_terminal()})"},
            {
                "status": "cancelled",
                "completed_at": _iso(datetime.now(UTC)),
                "worker_id": None,
                "lease_expires_at": None,
            },
        )
        return bool(rows)

    async def get_status(self, session_id: str) -> SessionStatus | None:
        rows = await self._req(
            "GET", "/research_sessions", params={"id": f"eq.{session_id}", "select": "status"}
        )
        return SessionStatus(rows[0]["status"]) if rows else None

    async def reset_run(self, session_id: str) -> None:
        """Clear outputs of an earlier, interrupted attempt so a retry starts clean."""
        sid = f"eq.{session_id}"
        await self._req("DELETE", "/evidence_records", params={"session_id": sid})
        await self._req("DELETE", "/research_reports", params={"session_id": sid})
        await self._req(
            "DELETE", "/agent_executions", params={"session_id": sid, "agent_name": "neq.research_planner"}
        )

    async def save_audit(self, session_id: str, audit: dict[str, Any]) -> None:
        await self._update_session(session_id, {"run_audit": audit})

    async def set_status(self, session_id: str, status: SessionStatus) -> None:
        # Progress updates never override a cancelled or finished session.
        await self._patch_where(
            {"id": f"eq.{session_id}", "status": f"not.in.({_terminal()})"}, {"status": status.value}
        )

    async def save_plan(self, session_id: str, plan: ResearchPlan) -> None:
        await self._update_session(session_id, {"research_plan": plan.model_dump(mode="json")})

    async def upsert_agent(self, session_id: str, execution: AgentExecution) -> None:
        await self._req(
            "POST",
            "/agent_executions",
            params={"on_conflict": "session_id,agent_name"},
            prefer="resolution=merge-duplicates",
            json={
                "session_id": session_id,
                "agent_name": execution.agent_name.value,
                "execution_status": execution.status.value,
                "execution_duration_ms": execution.duration_ms,
                "record_count": execution.record_count,
                "message": execution.message,
                "sources": [s.model_dump(mode="json") for s in execution.sources],
                "error_message": execution.error_message,
                "started_at": execution.started_at.isoformat() if execution.started_at else None,
                "completed_at": execution.completed_at.isoformat() if execution.completed_at else None,
            },
        )

    async def save_evidence(self, session_id: str, records: list[EvidenceRecord]) -> None:
        rows = [_evidence_to_row(session_id, i, r) for i, r in enumerate(records)]
        for start in range(0, len(rows), EVIDENCE_BATCH):
            await self._req(
                "POST",
                "/evidence_records",
                params={"on_conflict": "session_id,record_id"},
                prefer="resolution=merge-duplicates",
                json=rows[start : start + EVIDENCE_BATCH],
            )

    async def complete(
        self, session_id: str, report: ResearchReport, profile: dict[str, Any], warnings: list[str]
    ) -> None:
        ensure_publishable(report)  # no unverified report is ever stored
        summary = next((s for s in report.sections if s.key == "executive_summary"), None)
        await self._req(
            "POST",
            "/research_reports",
            params={"on_conflict": "session_id"},
            prefer="resolution=merge-duplicates",
            json={
                "session_id": session_id,
                "executive_summary": " ".join(st.text for st in summary.statements) if summary else None,
                "report_content": report.model_dump(mode="json"),
            },
        )
        await self._patch_where(
            {"id": f"eq.{session_id}", "status": "neq.cancelled"},
            {
                "status": "completed",
                "evidence_profile": profile,
                "warnings": warnings,
                "completed_at": datetime.now(UTC).isoformat(),
                "worker_id": None,
                "lease_expires_at": None,
            },
        )

    async def fail(
        self, session_id: str, error: str, profile: dict[str, Any] | None, warnings: list[str]
    ) -> None:
        await self._patch_where(
            {"id": f"eq.{session_id}", "status": "neq.cancelled"},
            {
                "status": "failed",
                "error_message": error[:1000],
                "evidence_profile": profile,
                "warnings": warnings,
                "completed_at": datetime.now(UTC).isoformat(),
                "worker_id": None,
                "lease_expires_at": None,
            },
        )

    # -- reads --------------------------------------------------------------------------------------------
    async def get_session(self, session_id: str) -> tuple[SessionDetail, str | None] | None:
        rows = await self._req(
            "GET",
            "/research_sessions",
            params={
                "id": f"eq.{session_id}",
                "select": "*,agent_executions(*),research_reports(report_content)",
            },
        )
        if not rows:
            return None
        row = rows[0]
        executions = {
            e["agent_name"]: AgentExecution(
                agent_name=e["agent_name"],
                status=e["execution_status"],
                started_at=e["started_at"],
                completed_at=e["completed_at"],
                duration_ms=e["execution_duration_ms"],
                record_count=e["record_count"],
                message=e["message"],
                error_message=e["error_message"],
                sources=e.get("sources") or [],
            )
            for e in row.get("agent_executions") or []
        }
        reports = row.get("research_reports")
        if isinstance(reports, list):
            reports = reports[0] if reports else None
        detail = SessionDetail(
            session_id=row["id"],
            research_question=row["research_question"],
            status=row["status"],
            demo_mode=row["demo_mode"],
            created_at=row["created_at"],
            completed_at=row["completed_at"],
            research_plan=row.get("research_plan"),
            agents=ordered_agents(executions),
            evidence_profile=row.get("evidence_profile"),
            warnings=row.get("warnings") or [],
            error_message=row.get("error_message"),
            report=ResearchReport.model_validate(reports["report_content"]) if reports else None,
            protocol_approved_at=row.get("protocol_approved_at"),
            attempts=row.get("attempts") or 0,
            run_audit=row.get("run_audit"),
        )
        return detail, row.get("user_id")

    async def get_evidence(self, session_id: str) -> list[EvidenceRecord]:
        rows = await self._req(
            "GET",
            "/evidence_records",
            params={"session_id": f"eq.{session_id}", "order": "position.asc", "select": "*"},
        )
        return [_row_to_evidence(r) for r in rows or []]

    async def list_sessions(self, user_id: str, limit: int = 50) -> list[SessionSummary]:
        rows = await self._req(
            "GET",
            "/research_sessions",
            params={
                "user_id": f"eq.{user_id}",
                "order": "created_at.desc",
                "limit": str(limit),
                "select": "id,research_question,status,demo_mode,created_at,completed_at,attempts",
            },
        )
        return [
            SessionSummary(
                session_id=r["id"],
                research_question=r["research_question"],
                status=r["status"],
                demo_mode=r["demo_mode"],
                created_at=r["created_at"],
                completed_at=r["completed_at"],
                attempts=r.get("attempts") or 0,
            )
            for r in rows or []
        ]


def _iso(dt: datetime) -> str:
    return dt.astimezone(UTC).isoformat()


def _terminal() -> str:
    return ",".join(s.value for s in TERMINAL_STATUSES)


def _evidence_to_row(session_id: str, position: int, r: EvidenceRecord) -> dict[str, Any]:
    return {
        "session_id": session_id,
        "record_id": r.record_id,
        "source_name": r.source_name.value,
        "source_identifier": r.source_identifier,
        "category": r.category.value,
        "title": r.title,
        "summary": r.summary,
        "evidence_type": r.evidence_type.value,
        "source_url": str(r.source_url),
        "publication_date": r.publication_date,
        "retrieved_at": r.retrieved_at.isoformat(),
        "position": position,
        "metadata": {
            "source_metadata": r.metadata,
            "identifiers": r.identifiers.model_dump(),
            "authors": r.authors,
            "journal": r.journal,
            "publication_types": r.publication_types,
            "quality_flags": [f.value for f in r.quality_flags],
            "also_found_in": [s.value for s in r.also_found_in],
            "provenance": r.provenance.model_dump() if r.provenance else None,
        },
    }


def _row_to_evidence(row: dict[str, Any]) -> EvidenceRecord:
    md = row.get("metadata") or {}
    return EvidenceRecord(
        record_id=row["record_id"],
        source_name=row["source_name"],
        source_identifier=row["source_identifier"],
        category=row["category"],
        evidence_type=row["evidence_type"],
        title=row["title"],
        summary=row["summary"],
        source_url=row["source_url"],
        publication_date=row["publication_date"],
        retrieved_at=row["retrieved_at"],
        identifiers=md.get("identifiers") or {},
        authors=md.get("authors") or [],
        journal=md.get("journal"),
        publication_types=md.get("publication_types") or [],
        metadata=md.get("source_metadata") or {},
        quality_flags=md.get("quality_flags") or [],
        also_found_in=md.get("also_found_in") or [],
        provenance=md.get("provenance"),
    )
