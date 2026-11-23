"""LangGraph orchestration of the PharmaLens agents, in two graphs separated by user approval.

    Planning graph:   START → planner → END                      (then the user reviews the protocol)

    Execution graph:  START ─┬─> literature ───────────────┐
                             ├─> clinical ──> compounds ───┼─> validation → synthesis → verification → END
                             └─> targets ──────────────────┘

Literature, clinical and target retrieval run in parallel. The compound agent waits for the clinical agent so
it can look up investigational products named in real trial registrations. A failure in one retrieval agent
is recorded and the workflow continues with partial evidence; planner or synthesis failure fails the session.
Nothing reaches `report` without passing the verification node, and repositories refuse unverified reports.
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
from app.agents.synthesis import MAX_RECORDS_IN_PROMPT, describe_scope, draft_report
from app.agents.targets import retrieve_targets
from app.agents.validation import validate_evidence
from app.agents.verification import profile_numbers, verify_report
from app.graph.progress import NullReporter, ProgressReporter
from app.graph.state import ResearchState
from app.integrations.http import SourceHttpClient
from app.models.agents import AgentExecution, AgentName, ExecutionStatus
from app.models.report import REPORT_SECTIONS
from app.models.research import ResearchPlan, SessionStatus

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
    openalex_api_key: str | None = None
    # Checked before each agent starts; returning True stops the run (user cancelled the job).
    should_stop: Callable[[], Awaitable[bool]] | None = None
    # IDs of evidence persisted for this session; citations outside it are rejected (ownership check).
    persisted_ids: Callable[[], Awaitable[set[str]]] | None = None
    semantic_verification: bool = True


def _tracked(
    agent: AgentName,
    deps: WorkflowDeps,
    body: Callable[[ResearchState, AgentExecution], Awaitable[dict[str, Any]]],
) -> NodeFn:
    """Wrap a node: time it, publish running/completed/failed states, and capture errors in state."""

    async def node(state: ResearchState) -> dict[str, Any]:
        if state.get("cancelled") or (deps.should_stop and await deps.should_stop()):
            skipped = AgentExecution(
                agent_name=agent, status=ExecutionStatus.SKIPPED, message="Run cancelled"
            )
            await deps.reporter.agent_updated(skipped)
            return {"cancelled": True, "agent_statuses": {agent.value: skipped}}
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


def build_workflow(deps: WorkflowDeps):  # noqa: ANN201 - returns (planning, execution) compiled graphs
    async def planner(state: ResearchState, ex: AgentExecution) -> dict[str, Any]:
        await deps.reporter.status_changed(SessionStatus.PLANNING)
        plan = await plan_research(deps.llm, state["research_question"])
        ex.message = plan.rationale or f"Query: {plan.literature_query}"
        await deps.reporter.plan_ready(plan)
        return {"research_plan": plan}

    async def literature(state: ResearchState, ex: AgentExecution) -> dict[str, Any]:
        result = await retrieve_literature(
            deps.http,
            state["research_plan"],
            ncbi_api_key=deps.ncbi_api_key,
            openalex_api_key=deps.openalex_api_key,
        )
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
        draft = await draft_report(
            deps.llm,
            question=state["research_question"],
            plan=state["research_plan"],
            records=state["validated_evidence"],
            profile=state["evidence_profile"],
        )
        drafted = sum(len(getattr(draft, k)) for k, _ in REPORT_SECTIONS)
        ex.record_count = drafted
        ex.message = f"Drafted {drafted} claims for verification"
        return {"draft": draft}

    async def verification(state: ResearchState, ex: AgentExecution) -> dict[str, Any]:
        records = state["validated_evidence"]
        persisted = await deps.persisted_ids() if deps.persisted_ids else None
        report = await verify_report(
            deps.llm if deps.semantic_verification else None,
            state["draft"],
            records,
            persisted_ids=persisted,
            context_numbers=profile_numbers(state.get("evidence_profile") or {}),
            question=state["research_question"],
            scope=describe_scope(
                state["research_plan"],
                state.get("evidence_profile") or {},
                sorted(set(state.get("failed_sources", []))),
            ),
            model=deps.model_name,
            records_provided=min(len(records), MAX_RECORDS_IN_PROMPT),
        )
        i = report.integrity
        published = i.statements_total - i.statements_removed_unsupported
        ex.record_count = published
        ex.message = (
            f"{published} of {i.statements_total} claims published, {len(report.references)} cited records; "
            f"removed {i.statements_removed_unsupported}, relabelled {len(i.relabelled)}, "
            f"dropped {i.citations_removed_invalid} citations; semantic check {i.semantic_check.replace('_', ' ')}"
        )
        return {"report": report}

    def fan_out(state: ResearchState) -> list[str] | str:
        return ["literature", "clinical", "targets"] if state.get("research_plan") else END

    def after_validation(state: ResearchState) -> str:
        return "synthesis" if state.get("validated_evidence") and not state.get("cancelled") else END

    planning = StateGraph(ResearchState)
    planning.add_node("planner", _tracked(AgentName.PLANNER, deps, planner))
    planning.add_edge(START, "planner")
    planning.add_edge("planner", END)

    execution = StateGraph(ResearchState)
    execution.add_node("literature", _tracked(AgentName.LITERATURE, deps, literature))
    execution.add_node("clinical", _tracked(AgentName.CLINICAL, deps, clinical))
    execution.add_node("targets", _tracked(AgentName.TARGETS, deps, targets))
    execution.add_node("compounds", _tracked(AgentName.COMPOUNDS, deps, compounds))
    execution.add_node("validation", _tracked(AgentName.VALIDATION, deps, validation))
    execution.add_node("synthesis", _tracked(AgentName.SYNTHESIS, deps, synthesis))
    execution.add_conditional_edges(START, fan_out, ["literature", "clinical", "targets", END])
    execution.add_edge("clinical", "compounds")
    execution.add_edge(["literature", "targets", "compounds"], "validation")
    execution.add_node("verification", _tracked(AgentName.VERIFICATION, deps, verification))
    execution.add_conditional_edges("validation", after_validation, ["synthesis", END])
    execution.add_conditional_edges(
        "synthesis",
        lambda st: "verification" if st.get("draft") and not st.get("cancelled") else END,
        ["verification", END],
    )
    execution.add_edge("verification", END)
    return planning.compile(), execution.compile()


def _initial(session_id: str, question: str, plan: ResearchPlan | None) -> ResearchState:
    return {
        "session_id": session_id,
        "research_question": question,
        "research_plan": plan,
        "agent_statuses": {},
        "errors": [],
        "warnings": [],
        "failed_sources": [],
        "report": None,
        "cancelled": False,
    }


async def run_planning(deps: WorkflowDeps, session_id: str, question: str) -> ResearchState:
    """Draft the research protocol only. The user reviews and approves it before execution."""
    planning, _ = build_workflow(deps)
    return await planning.ainvoke(_initial(session_id, question, None))


async def run_execution(
    deps: WorkflowDeps, session_id: str, question: str, plan: ResearchPlan
) -> ResearchState:
    """Retrieve, validate and synthesise using an approved protocol."""
    _, execution = build_workflow(deps)
    await deps.reporter.status_changed(SessionStatus.RESEARCHING)
    return await execution.ainvoke(_initial(session_id, question, plan))


async def run_research(deps: WorkflowDeps, session_id: str, question: str) -> ResearchState:
    """Planning then execution with the plan as drafted (no review step). Used by tests and scripts."""
    planned = await run_planning(deps, session_id, question)
    plan = planned.get("research_plan")
    if plan is None:
        return planned
    executed = await run_execution(deps, session_id, question, plan)
    executed["agent_statuses"] = {**planned.get("agent_statuses", {}), **executed.get("agent_statuses", {})}
    executed["errors"] = [*planned.get("errors", []), *executed.get("errors", [])]
    return executed
