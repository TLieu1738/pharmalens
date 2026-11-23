"""Durable job execution: claiming, lease expiry, recovery after a crash, bounded retries, cancellation."""

import pytest

from app.config import Settings
from app.models.research import ResearchPlan, SessionStatus
from app.services.repository import InMemorySessionRepository
from app.services.research_service import JobRunner, ResearchService
from tests.fakes import PLAN, FakeLLM, source_router
from tests.helpers import mock_http

QUESTION = "Investigate Alzheimer's disease research focusing on amyloid-beta and tau."


def _plan() -> ResearchPlan:
    return ResearchPlan(**PLAN.model_dump())


def _settings() -> Settings:
    return Settings(_env_file=None, environment="test", job_max_attempts=2, job_lease_seconds=30)


async def test_claims_are_exclusive_and_leases_expire() -> None:
    repo = InMemorySessionRepository()
    sid = await repo.create_session(QUESTION, "u1", demo_mode=False)
    job = await repo.claim_job("w1", 30)
    assert job and job.session_id == sid and job.phase == "plan" and job.attempts == 1
    assert await repo.claim_job("w2", 30) is None  # already leased
    assert await repo.renew_lease(sid, "w1", 30)
    assert not await repo.renew_lease(sid, "w2", 30)  # only the owner of the lease can renew it


async def test_interrupted_job_is_requeued_then_failed_after_max_attempts() -> None:
    repo = InMemorySessionRepository()
    sid = await repo.create_session(QUESTION, "u1", demo_mode=False, plan=_plan())
    assert await repo.approve(sid, _plan())

    job = await repo.claim_job("dead-worker", 30)
    assert job and job.phase == "execute"
    repo.expire_lease(sid)  # the worker died mid-run
    assert await repo.recover_stale(max_attempts=2) == (1, 0)
    assert await repo.get_status(sid) == SessionStatus.QUEUED  # back in the queue, plan kept

    job = await repo.claim_job("dead-again", 30)
    assert job and job.attempts == 2
    repo.expire_lease(sid)
    assert await repo.recover_stale(max_attempts=2) == (0, 1)
    detail, _ = await repo.get_session(sid)  # type: ignore[misc]
    assert detail.status == SessionStatus.FAILED and "2 attempts" in (detail.error_message or "")


async def test_runner_resumes_a_job_left_by_a_crashed_worker() -> None:
    repo = InMemorySessionRepository()
    settings = _settings()
    async with mock_http(source_router()) as http:
        service = ResearchService(settings, repo, http, FakeLLM())
        sid = await repo.create_session(QUESTION, "u1", demo_mode=False, plan=_plan())
        await repo.approve(sid, _plan())
        crashed = await repo.claim_job("crashed-worker", 30)
        assert crashed is not None
        repo.expire_lease(sid)

        runner = JobRunner(settings, repo, http, service)
        requeued, _ = await repo.recover_stale(settings.job_max_attempts)
        assert requeued == 1
        job = await repo.claim_job(runner.worker_id, 30)
        assert job and job.attempts == 2
        await runner._run(job)

    detail, _ = await repo.get_session(sid)  # type: ignore[misc]
    assert detail.status == SessionStatus.COMPLETED
    assert detail.report is not None
    assert detail.run_audit and detail.run_audit["attempts"] == 2


async def test_cancelled_run_stops_and_is_not_overwritten() -> None:
    repo = InMemorySessionRepository()
    settings = _settings()
    async with mock_http(source_router()) as http:
        service = ResearchService(settings, repo, http, FakeLLM())
        sid = await repo.create_session(QUESTION, "u1", demo_mode=False, plan=_plan())
        await repo.approve(sid, _plan())
        job = await repo.claim_job("w1", 30)
        assert job is not None
        assert await repo.cancel(sid)
        await JobRunner(settings, repo, http, service)._run(job)

    detail, _ = await repo.get_session(sid)  # type: ignore[misc]
    assert detail.status == SessionStatus.CANCELLED
    assert detail.report is None
    assert all(
        a.status.value in ("skipped", "pending")
        for a in detail.agents
        if a.agent_name.value != "research_planner"
    )


@pytest.mark.parametrize("phase_status", [SessionStatus.PENDING, SessionStatus.QUEUED])
async def test_claim_phase_follows_status(phase_status: SessionStatus) -> None:
    repo = InMemorySessionRepository()
    plan = _plan() if phase_status == SessionStatus.QUEUED else None
    sid = await repo.create_session(QUESTION, "u1", demo_mode=False, plan=plan)
    if plan:
        await repo.approve(sid, plan)
    job = await repo.claim_job("w", 30)
    assert job and job.phase == ("plan" if phase_status == SessionStatus.PENDING else "execute")
