"""Research jobs: creation, protocol approval and durable background execution.

Execution model
---------------
Every research session is also a job record in the database. The API only *enqueues* work (creates a
`pending` session, or moves an approved one to `queued`); a `JobRunner` claims due jobs with a time-limited
lease, runs the LangGraph stage, and renews the lease while it works. If the process dies, the lease lapses
and `recover_stale` puts the job back in the queue (up to `job_max_attempts`), so a restart does not lose
research. The runner runs inside the API process by default; `python -m app.worker` runs the same loop as a
separate worker process, and several can run at once because claims are atomic.
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from collections import defaultdict, deque
from datetime import UTC, datetime
from typing import Any

from app.agents.llm import AnthropicLLM, LLMNotConfiguredError, StructuredLLM
from app.config import Settings
from app.graph.state import ResearchState
from app.graph.workflow import WorkflowDeps, run_execution, run_planning
from app.integrations.http import SourceHttpClient
from app.models.agents import AgentExecution
from app.models.evidence import EvidenceRecord
from app.models.research import ResearchPlan, SessionStatus
from app.services.repository import ClaimedJob, SessionRepository

logger = logging.getLogger(__name__)

PLANNER_EFFORT = "low"
SYNTHESIS_EFFORT = "medium"


class CapacityError(Exception):
    """The caller hit the anonymous rate limit."""


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


def build_audit(
    state: ResearchState, *, model: str, attempts: int, started: datetime, plan: ResearchPlan
) -> dict[str, Any]:
    """What happened in a run, for the reproducibility / audit view. No secrets or prompts."""
    retrieved = sum(
        len(state.get(k) or [])
        for k in ("literature_records", "clinical_records", "target_records", "compound_records")
    )
    validated = state.get("validated_evidence") or []
    merges = [
        {
            "kept": r.record_id,
            "merged": [m for m in r.metadata.get("merged_record_ids", []) if m != r.record_id],
        }
        for r in validated
        if len(r.metadata.get("merged_record_ids", [])) > 1
    ]
    return {
        "model": {"id": model, "planner_effort": PLANNER_EFFORT, "synthesis_effort": SYNTHESIS_EFFORT},
        "attempts": attempts,
        "execution_started_at": started.isoformat(),
        "execution_finished_at": datetime.now(UTC).isoformat(),
        "limits": {
            "max_results_per_source": plan.max_results_per_source,
            "literature_queries": plan.literature_queries,
            "date_from": plan.date_from,
            "date_to": plan.date_to,
            "include_preprints": plan.include_preprints,
        },
        "deduplication": {
            "records_retrieved": retrieved,
            "unique_records": len(validated),
            "duplicates_merged": retrieved - len(validated) if validated else 0,
            "merges": merges[:200],
        },
        "errors": list(dict.fromkeys(state.get("errors") or [])),
    }


class ResearchService:
    """API-facing operations. Never runs research itself: it enqueues and wakes the runner."""

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
        self._anon_hits: dict[str, deque[float]] = defaultdict(deque)
        self.wake = asyncio.Event()

    def get_llm(self) -> StructuredLLM:
        if self._llm is None:
            try:
                self._llm = AnthropicLLM(self._settings)
            except LLMNotConfiguredError as exc:
                raise ServiceUnavailableError("The AI service is not configured on this server.") from exc
        return self._llm

    def _check_anonymous_quota(self, client_key: str) -> None:
        window = self._anon_hits[client_key]
        now = time.monotonic()
        while window and now - window[0] > 3600:
            window.popleft()
        if len(window) >= self._settings.anon_sessions_per_hour:
            raise CapacityError("Hourly limit for signed-out research reached. Sign in or try again later.")
        window.append(now)

    async def start(
        self, question: str, user_id: str | None, client_key: str, plan: ResearchPlan | None = None
    ) -> str:
        """Create a session. Without a plan it is queued for planning; with one it awaits approval."""
        self.get_llm()  # fail fast (503) if the AI service is not configured
        if user_id is None:
            self._check_anonymous_quota(client_key)
        session_id = await self._repo.create_session(question, user_id, demo_mode=user_id is None, plan=plan)
        self.wake.set()
        logger.info("research_created session_id=%s authenticated=%s", session_id, user_id is not None)
        return session_id

    async def approve(self, session_id: str, plan: ResearchPlan) -> bool:
        ok = await self._repo.approve(session_id, plan)
        if ok:
            self.wake.set()
            logger.info("protocol_approved session_id=%s", session_id)
        return ok


class JobRunner:
    """Claims due jobs from the repository and runs them with bounded concurrency."""

    def __init__(
        self, settings: Settings, repo: SessionRepository, http: SourceHttpClient, service: ResearchService
    ) -> None:
        self._settings = settings
        self._repo = repo
        self._http = http
        self._service = service
        self.worker_id = f"worker-{uuid.uuid4().hex[:8]}"
        self._tasks: set[asyncio.Task[None]] = set()
        self._stopping = False

    @property
    def running(self) -> int:
        return len(self._tasks)

    async def run_forever(self) -> None:
        logger.info("job_runner_started worker_id=%s", self.worker_id)
        while not self._stopping:
            try:
                requeued, failed = await self._repo.recover_stale(self._settings.job_max_attempts)
                if requeued or failed:
                    logger.warning("jobs_recovered requeued=%d failed=%d", requeued, failed)
                while self.running < self._settings.max_concurrent_research:
                    job = await self._repo.claim_job(self.worker_id, self._settings.job_lease_seconds)
                    if job is None:
                        break
                    task = asyncio.create_task(self._run(job), name=f"job-{job.session_id}")
                    self._tasks.add(task)
                    task.add_done_callback(self._tasks.discard)
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("job_runner_poll_failed")
            self._service.wake.clear()
            try:
                await asyncio.wait_for(self._service.wake.wait(), timeout=self._settings.job_poll_seconds)
            except TimeoutError:
                pass

    async def _heartbeat(self, session_id: str) -> None:
        interval = max(1.0, self._settings.job_lease_seconds / 3)
        while True:
            await asyncio.sleep(interval)
            try:
                if not await self._repo.renew_lease(
                    session_id, self.worker_id, self._settings.job_lease_seconds
                ):
                    return  # job cancelled or taken over; the run notices via should_stop
            except Exception:
                logger.exception("lease_renew_failed session_id=%s", session_id)

    def _deps(self, job: ClaimedJob, llm: StructuredLLM) -> WorkflowDeps:
        async def should_stop() -> bool:
            return await self._repo.get_status(job.session_id) == SessionStatus.CANCELLED

        return WorkflowDeps(
            llm=llm,
            http=self._http,
            model_name=getattr(llm, "model", None) or self._settings.anthropic_model or "unspecified",
            reporter=RepositoryReporter(self._repo, job.session_id),
            ncbi_api_key=self._settings.ncbi_api_key.get_secret_value()
            if self._settings.ncbi_api_key
            else None,
            should_stop=should_stop,
        )

    async def _run(self, job: ClaimedJob) -> None:
        heartbeat = asyncio.create_task(self._heartbeat(job.session_id))
        started = time.perf_counter()
        logger.info("job_started session_id=%s phase=%s attempt=%d", job.session_id, job.phase, job.attempts)
        try:
            deps = self._deps(job, self._service.get_llm())
            if job.phase == "plan":
                await self._plan(job, deps)
            else:
                await self._execute(job, deps)
        except Exception:
            logger.exception("job_crashed session_id=%s", job.session_id)
            await self._repo.fail(job.session_id, "Unexpected server error during research.", None, [])
        finally:
            heartbeat.cancel()
            logger.info(
                "job_finished session_id=%s phase=%s elapsed_s=%.1f",
                job.session_id,
                job.phase,
                time.perf_counter() - started,
            )

    async def _plan(self, job: ClaimedJob, deps: WorkflowDeps) -> None:
        state = await run_planning(deps, job.session_id, job.question)
        if state.get("research_plan") is not None:
            await self._repo.finish_planning(job.session_id)
        elif not state.get("cancelled"):
            errors = state.get("errors") or ["the research protocol could not be drafted"]
            await self._repo.fail(job.session_id, "; ".join(errors), None, [])

    async def _execute(self, job: ClaimedJob, deps: WorkflowDeps) -> None:
        if job.plan is None:
            await self._repo.fail(job.session_id, "No approved protocol to execute.", None, [])
            return
        await self._repo.reset_run(job.session_id)  # a retry starts from a clean slate
        started = datetime.now(UTC)
        state = await run_execution(deps, job.session_id, job.question, job.plan)
        if state.get("cancelled"):
            return
        warnings = list(dict.fromkeys(state.get("warnings", [])))
        profile = state.get("evidence_profile")
        report = state.get("report")
        await self._repo.save_audit(
            job.session_id,
            build_audit(state, model=deps.model_name, attempts=job.attempts, started=started, plan=job.plan),
        )
        if report is not None:
            await self._repo.complete(job.session_id, report, profile or {}, warnings)
        else:
            errors = state.get("errors") or ["research could not be completed"]
            await self._repo.fail(job.session_id, "; ".join(errors), profile, warnings)

    async def shutdown(self) -> None:
        """Stop claiming and cancel in-flight runs. Their leases lapse and another worker resumes them."""
        self._stopping = True
        for task in list(self._tasks):
            task.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)
