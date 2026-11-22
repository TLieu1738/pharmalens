"""LangGraph orchestration of the PharmaLens agents.

    START → planner ─┬─> literature ───────────────┐
                     ├─> clinical ──> compounds ───┼─> validation → synthesis → END
                     └─> targets ──────────────────┘

Literature, clinical and target retrieval run in parallel. The compound agent waits for the clinical agent so
it can look up investigational products named in real trial registrations. A failure in one retrieval agent
is recorded and the workflow continues with partial evidence; planner or synthesis failure fails the session.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from langgraph.graph import END, START, StateGraph

from app.agents.base import RetrievalResult
from app.agents.clinical import retrieve_trials
from app.agents.compounds import retrieve_compounds
from app.agents.literature import retrieve_literature
from app.agents.llm import LLMError, StructuredLLM
from app.agents.planner import plan_research
from app.agents.synthesis import synthesise_report
from app.agents.targets import retrieve_targets
from app.agents.validation import validate_evidence
from app.graph.progress import NullReporter, ProgressReporter
from app.graph.state import ResearchState
from app.integrations.http import SourceHttpClient
from app.models.agents import AgentExecution, AgentName, ExecutionStatus
from app.models.research import SessionStatus

logger = logging.getLogger(__name__)

NodeFn = Callable[[ResearchState], Awaitable[dict[str, Any]]]


class WorkflowError(Exception):
    """A required step failed; the message is safe to show to users."""


@dataclass
class WorkflowDeps:
    llm: StructuredLLM
    http: SourceHttpClient
    model_name: str
    reporter: ProgressReporter = NullReporter()  # type: ignore[assignment]
    ncbi_api_key: str | None = None


def _tracked(
    agent: AgentName,
    deps: WorkflowDeps,
    body: Callable[[ResearchState, AgentExecution], Awaitable[dict[str, Any]]],
) -> NodeFn:
    """Wrap a node: time it, publish running/completed/failed states, and capture errors in state."""

    async def node(state: ResearchState) -> dict[str, Any]:
        execution = AgentExecution(
            agent_name=agent, status=ExecutionStatus.RUNNING, started_at=datetime.now(UTC)
        )
        await deps.reporter.agent_updated(execution)
        started = time.perf_counter()
        try:
            update = await body(state, execution)
            if execution.status == ExecutionStatus.RUNNING:
                execution.status = ExecutionStatus.COMPLETED
        except Exception as exc:
            execution.status = ExecutionStatus.FAILED
            safe = str(exc) if isinstance(exc, (LLMError, WorkflowError)) else "unexpected error"
            execution.error_message = safe
            logger.exception("agent_failed agent=%s", agent.value)
            update = {"errors": [f"{agent.value}: {safe}"]}
        execution.completed_at = datetime.now(UTC)
        execution.duration_ms = int((time.perf_counter() - started) * 1000)
        await deps.reporter.agent_updated(execution)
        update.setdefault("agent_statuses", {})[agent.value] = execution
        logger.info(
            "agent_done agent=%s status=%s duration_ms=%d records=%s",
            agent.value,
            execution.status.value,
            execution.duration_ms,
            execution.record_count,
        )
        return update

    return node


def _apply_retrieval(execution: AgentExecution, result: RetrievalResult) -> dict[str, Any]:
    execution.record_count = len(result.records)
    execution.sources = result.sources
    execution.message = result.message
    failed = [s.source for s in result.sources if not s.ok]
    if result.all_failed:
        execution.status = ExecutionStatus.FAILED
        execution.error_message = "; ".join(f"{s.source}: {s.error}" for s in result.sources if not s.ok)
    elif failed:
        execution.status = ExecutionStatus.PARTIAL
        execution.error_message = "; ".join(f"{s.source}: {s.error}" for s in result.sources if not s.ok)
    elif not result.sources:
        execution.status = ExecutionStatus.SKIPPED
    warnings = list(result.warnings) + [f"Source unavailable: {s}" for s in failed]
    return {"warnings": warnings, "failed_sources": failed}


def build_workflow(deps: WorkflowDeps):  # noqa: ANN201 - returns a compiled LangGraph
    async def planner(state: ResearchState, ex: AgentExecution) -> dict[str, Any]:
        await deps.reporter.status_changed(SessionStatus.PLANNING)
        plan = await plan_research(deps.llm, state["research_question"])
        ex.message = plan.rationale or f"Query: {plan.literature_query}"
        await deps.reporter.plan_ready(plan)
        await deps.reporter.status_changed(SessionStatus.RESEARCHING)
        return {"research_plan": plan}

    async def literature(state: ResearchState, ex: AgentExecution) -> dict[str, Any]:
        result = await retrieve_literature(deps.http, state["research_plan"], ncbi_api_key=deps.ncbi_api_key)
        return {"literature_records": result.records, **_apply_retrieval(ex, result)}

    async def clinical(state: ResearchState, ex: AgentExecution) -> dict[str, Any]:
        result = await retrieve_trials(deps.http, state["research_plan"])
        return {"clinical_records": result.records, **_apply_retrieval(ex, result)}

    async def targets(state: ResearchState, ex: AgentExecution) -> dict[str, Any]:
        result = await retrieve_targets(deps.http, state["research_plan"])
        return {"target_records": result.records, **_apply_retrieval(ex, result)}

    async def compounds(state: ResearchState, ex: AgentExecution) -> dict[str, Any]:
        result = await retrieve_compounds(
            deps.http, state["research_plan"], state.get("clinical_records", [])
        )
        return {"compound_records": result.records, **_apply_retrieval(ex, result)}

    async def validation(state: ResearchState, ex: AgentExecution) -> dict[str, Any]:
        await deps.reporter.status_changed(SessionStatus.VALIDATING)
        combined = [
            *state.get("literature_records", []),
            *state.get("clinical_records", []),
            *state.get("target_records", []),
            *state.get("compound_records", []),
        ]
        if not combined:
            raise WorkflowError("no evidence could be retrieved from any source")
        result = validate_evidence(combined)
        ex.record_count = len(result.records)
        ex.message = (
            f"{len(combined)} records in, {result.duplicates_removed} duplicates merged, "
            f"{sum(len(r.quality_flags) for r in result.records)} quality flags raised"
        )
        await deps.reporter.evidence_ready(result.records)
        return {
            "validated_evidence": result.records,
            "evidence_profile": result.profile,
            "warnings": result.warnings,
        }

    async def synthesis(state: ResearchState, ex: AgentExecution) -> dict[str, Any]:
        await deps.reporter.status_changed(SessionStatus.SYNTHESISING)
        report = await synthesise_report(
            deps.llm,
            question=state["research_question"],
            plan=state["research_plan"],
            records=state["validated_evidence"],
            profile=state["evidence_profile"],
            failed_sources=sorted(set(state.get("failed_sources", []))),
            model_name=deps.model_name,
        )
        ex.record_count = len(report.references)
        integrity = report.integrity
        ex.message = (
            f"{integrity.statements_total - integrity.statements_removed_unsupported} statements, "
            f"{len(report.references)} cited records"
        )
        if integrity.statements_removed_unsupported or integrity.citations_removed_invalid:
            ex.message += (
                f"; removed {integrity.statements_removed_unsupported} unsupported statements and "
                f"{integrity.citations_removed_invalid} invalid citations"
            )
        return {"report": report}

    def after_planner(state: ResearchState) -> list[str] | str:
        return ["literature", "clinical", "targets"] if state.get("research_plan") else END

    def after_validation(state: ResearchState) -> str:
        return "synthesis" if state.get("validated_evidence") else END

    graph = StateGraph(ResearchState)
    graph.add_node("planner", _tracked(AgentName.PLANNER, deps, planner))
    graph.add_node("literature", _tracked(AgentName.LITERATURE, deps, literature))
    graph.add_node("clinical", _tracked(AgentName.CLINICAL, deps, clinical))
    graph.add_node("targets", _tracked(AgentName.TARGETS, deps, targets))
    graph.add_node("compounds", _tracked(AgentName.COMPOUNDS, deps, compounds))
    graph.add_node("validation", _tracked(AgentName.VALIDATION, deps, validation))
    graph.add_node("synthesis", _tracked(AgentName.SYNTHESIS, deps, synthesis))

    graph.add_edge(START, "planner")
    graph.add_conditional_edges("planner", after_planner, ["literature", "clinical", "targets", END])
    graph.add_edge("clinical", "compounds")
    graph.add_edge(["literature", "targets", "compounds"], "validation")
    graph.add_conditional_edges("validation", after_validation, ["synthesis", END])
    graph.add_edge("synthesis", END)
    return graph.compile()


async def run_research(deps: WorkflowDeps, session_id: str, question: str) -> ResearchState:
    workflow = build_workflow(deps)
    initial: ResearchState = {
        "session_id": session_id,
        "research_question": question,
        "research_plan": None,
        "agent_statuses": {},
        "errors": [],
        "warnings": [],
        "failed_sources": [],
        "report": None,
    }
    return await workflow.ainvoke(initial)
