"""Progress reporting interface so the workflow can publish real agent states as they happen."""

from typing import Protocol

from app.models.agents import AgentExecution
from app.models.evidence import EvidenceRecord
from app.models.research import ResearchPlan, SessionStatus


class ProgressReporter(Protocol):
    async def status_changed(self, status: SessionStatus) -> None: ...

    async def agent_updated(self, execution: AgentExecution) -> None: ...

    async def plan_ready(self, plan: ResearchPlan) -> None: ...

    async def evidence_ready(self, records: list[EvidenceRecord]) -> None: ...


class NullReporter:
    async def status_changed(self, status: SessionStatus) -> None:
        return None

    async def agent_updated(self, execution: AgentExecution) -> None:
        return None

    async def plan_ready(self, plan: ResearchPlan) -> None:
        return None

    async def evidence_ready(self, records: list[EvidenceRecord]) -> None:
        return None
