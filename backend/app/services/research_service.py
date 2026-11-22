"""Creates research sessions and runs the LangGraph workflow in the background.

Execution model: an in-process asyncio task per session. This keeps deployment to a single Render web
service. It is NOT durable — if the server restarts mid-run, the session is marked failed on startup
(see `SessionRepository.fail_interrupted`). A queue + separate worker is the documented upgrade path.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections import defaultdict, deque
from typing import Any

from app.agents.llm import ClaudeLLM, LLMNotConfiguredError, StructuredLLM
from app.config import Settings
from app.graph.workflow import WorkflowDeps, run_research
from app.integrations.http import SourceHttpClient
from app.models.agents import AgentExecution
from app.models.evidence import EvidenceRecord
from app.models.research import ResearchPlan, SessionStatus
from app.services.repository import SessionRepository

logger = logging.getLogger(__name__)


class CapacityError(Exception):
    """Too many sessions running, or the caller hit the anonymous rate limit."""


class ServiceUnavailableError(Exception):
    pass


class RepositoryReporter:
    """Publishes workflow progress to the session repository as it happens."""

    def __init__(self, repo: SessionRepository, session_id: str) -> None:
        self._repo, self._sid = repo, session_id

    async def _safe(self, coro: Any) -> None:
        try:
            await coro
        except Exception:  # progress persistence must never crash the research run
            logger.exception("progress_persist_failed session_id=%s", self._sid)

    async def status_changed(self, status: SessionStatus) -> None:
        await self._safe(self._repo.set_status(self._sid, status))

    async def agent_updated(self, execution: AgentExecution) -> None:
        await self._safe(self._repo.upsert_agent(self._sid, execution))

    async def plan_ready(self, plan: ResearchPlan) -> None:
        await self._safe(self._repo.save_plan(self._sid, plan))

    async def evidence_ready(self, records: list[EvidenceRecord]) -> None:
        await self._safe(self._repo.save_evidence(self._sid, records))


class ResearchService:
    def __init__(
        self,
        settings: Settings,
        repo: SessionRepository,
        http: SourceHttpClient,
        llm: StructuredLLM | None = None,
    ) -> None:
        self._settings = settings
        self._repo = repo
        self._http = http
        self._llm = llm
        self._tasks: set[asyncio.Task[None]] = set()
        self._anon_hits: dict[str, deque[float]] = defaultdict(deque)

    def _get_llm(self) -> StructuredLLM:
        if self._llm is None:
            try:
                self._llm = ClaudeLLM(self._settings)
            except LLMNotConfiguredError as exc:
                raise ServiceUnavailableError("The AI service is not configured on this server.") from exc
        return self._llm

    @property
    def running(self) -> int:
        return len(self._tasks)

    def _check_anonymous_quota(self, client_key: str) -> None:
        window = self._anon_hits[client_key]
        now = time.monotonic()
        while window and now - window[0] > 3600:
            window.popleft()
        if len(window) >= self._settings.anon_sessions_per_hour:
            raise CapacityError("Hourly limit for signed-out research reached. Sign in or try again later.")
        window.append(now)

    async def start(self, question: str, user_id: str | None, client_key: str) -> str:
        llm = self._get_llm()
        if self.running >= self._settings.max_concurrent_research:
            raise CapacityError("PharmaLens is busy with other research right now. Please retry in a minute.")
        if user_id is None:
            self._check_anonymous_quota(client_key)
        session_id = await self._repo.create_session(question, user_id, demo_mode=user_id is None)
        task = asyncio.create_task(self._run(session_id, question, llm), name=f"research-{session_id}")
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)
        logger.info("research_started session_id=%s authenticated=%s", session_id, user_id is not None)
        return session_id

    async def _run(self, session_id: str, question: str, llm: StructuredLLM) -> None:
        deps = WorkflowDeps(
            llm=llm,
            http=self._http,
            model_name=getattr(llm, "model", self._settings.anthropic_model),
            reporter=RepositoryReporter(self._repo, session_id),
            ncbi_api_key=self._settings.ncbi_api_key.get_secret_value()
            if self._settings.ncbi_api_key
            else None,
        )
        started = time.perf_counter()
        try:
            state = await run_research(deps, session_id, question)
            warnings = list(dict.fromkeys(state.get("warnings", [])))
            profile = state.get("evidence_profile")
            report = state.get("report")
            if report is not None:
                await self._repo.complete(session_id, report, profile or {}, warnings)
            else:
                errors = state.get("errors") or ["research could not be completed"]
                await self._repo.fail(session_id, "; ".join(errors), profile, warnings)
        except Exception:
            logger.exception("research_crashed session_id=%s", session_id)
            await self._repo.fail(session_id, "Unexpected server error during research.", None, [])
        finally:
            logger.info(
                "research_finished session_id=%s elapsed_s=%.1f", session_id, time.perf_counter() - started
            )

    async def shutdown(self) -> None:
        for task in list(self._tasks):
            task.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)
