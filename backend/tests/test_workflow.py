"""Full LangGraph workflow with mocked sources and a mocked Claude."""

from app.agents.synthesis import SynthesisOutput
from app.graph.workflow import WorkflowDeps, run_research
from app.models.agents import AgentExecution, AgentName, ExecutionStatus
from app.models.report import StatementKind
from app.models.research import ResearchPlan, SessionStatus
from tests.fakes import FakeLLM, source_router
from tests.helpers import mock_http

QUESTION = "Investigate Alzheimer's disease research focusing on amyloid-beta and tau."


class RecordingReporter:
    def __init__(self) -> None:
        self.statuses: list[SessionStatus] = []
        self.updates: list[tuple[str, str]] = []
        self.plan: ResearchPlan | None = None
        self.evidence_count = 0

    async def status_changed(self, status: SessionStatus) -> None:
        self.statuses.append(status)

    async def agent_updated(self, execution: AgentExecution) -> None:
        self.updates.append((execution.agent_name.value, execution.status.value))

    async def plan_ready(self, plan: ResearchPlan) -> None:
        self.plan = plan

    async def evidence_ready(self, records: list) -> None:  # type: ignore[type-arg]
        self.evidence_count = len(records)


async def test_complete_workflow_produces_grounded_report() -> None:
    llm, reporter = FakeLLM(), RecordingReporter()
    async with mock_http(source_router()) as http:
        state = await run_research(
            WorkflowDeps(llm=llm, http=http, model_name="fake", reporter=reporter), "s1", QUESTION
        )

    assert llm.calls == ["PlannerOutput", "SynthesisOutput"]
    statuses = state["agent_statuses"]
    assert set(statuses) == {a.value for a in AgentName}
    assert all(s.status == ExecutionStatus.COMPLETED for s in statuses.values()), statuses
    assert statuses[AgentName.LITERATURE.value].record_count == 5  # 2 PubMed + 3 Europe PMC
    assert statuses[AgentName.COMPOUNDS.value].record_count == 1  # lecanemab exact match

    evidence = state["validated_evidence"]
    sources = {r.source_name.value for r in evidence}
    assert sources == {"pubmed", "europe_pmc", "clinicaltrials_gov", "chembl", "open_targets"}

    report = state["report"]
    assert report is not None
    # Fabricated citation and the uncited "finding" were removed by grounding.
    assert report.integrity.citations_removed_invalid == 1
    assert report.integrity.statements_removed_unsupported == 1
    exec_summary = next(s for s in report.sections if s.key == "executive_summary")
    assert [st.text for st in exec_summary.statements] == ["APP is the top-ranked Open Targets association."]
    gaps = next(s for s in report.sections if s.key == "research_gaps")
    assert gaps.statements[0].kind == StatementKind.GAP
    # Every reference maps to a retrieved record with its real URL.
    evidence_ids = {r.record_id: str(r.source_url) for r in evidence}
    assert report.references and all(
        evidence_ids[ref.record_id] == ref.source_url for ref in report.references
    )
    assert [r.number for r in report.references] == list(range(1, len(report.references) + 1))

    # Synthesis prompt only contains retrieved record ids.
    assert "pubmed:39776249" in llm.prompts[1]
    assert reporter.statuses == [
        SessionStatus.PLANNING,
        SessionStatus.RESEARCHING,
        SessionStatus.VALIDATING,
        SessionStatus.SYNTHESISING,
    ]
    assert ("research_planner", "running") in reporter.updates
    assert reporter.plan is not None and reporter.evidence_count == len(evidence)


async def test_source_outage_gives_partial_results_not_failure() -> None:
    llm = FakeLLM()
    async with mock_http(source_router(fail_hosts={"clinicaltrials.gov"}), max_retries=0) as http:
        state = await run_research(WorkflowDeps(llm=llm, http=http, model_name="fake"), "s2", QUESTION)
    statuses = state["agent_statuses"]
    assert statuses[AgentName.CLINICAL.value].status == ExecutionStatus.FAILED
    assert statuses[AgentName.LITERATURE.value].status == ExecutionStatus.COMPLETED
    assert state["report"] is not None
    assert "clinicaltrials_gov" in state["failed_sources"]
    assert any("clinicaltrials_gov" in w for w in state["warnings"])
    assert "Unavailable during this run: clinicaltrials_gov" in state["report"].scope


async def test_partial_status_when_one_literature_source_fails() -> None:
    async with mock_http(source_router(fail_hosts={"eutils.ncbi.nlm.nih.gov"}), max_retries=0) as http:
        state = await run_research(WorkflowDeps(llm=FakeLLM(), http=http, model_name="fake"), "s3", QUESTION)
    lit = state["agent_statuses"][AgentName.LITERATURE.value]
    assert lit.status == ExecutionStatus.PARTIAL and lit.record_count == 3


async def test_planner_failure_stops_workflow_cleanly() -> None:
    from app.agents.planner import PlannerOutput

    llm = FakeLLM(fail_on=PlannerOutput)
    async with mock_http(source_router()) as http:
        state = await run_research(WorkflowDeps(llm=llm, http=http, model_name="fake"), "s4", QUESTION)
    assert state["agent_statuses"][AgentName.PLANNER.value].status == ExecutionStatus.FAILED
    assert state.get("report") is None
    assert len(state["agent_statuses"]) == 1
    assert state["errors"] == ["research_planner: simulated failure"]


async def test_synthesis_failure_recorded() -> None:
    llm = FakeLLM(fail_on=SynthesisOutput)
    async with mock_http(source_router()) as http:
        state = await run_research(WorkflowDeps(llm=llm, http=http, model_name="fake"), "s5", QUESTION)
    assert state["agent_statuses"][AgentName.SYNTHESIS.value].status == ExecutionStatus.FAILED
    assert state["report"] is None and state["validated_evidence"]


async def test_all_sources_down_fails_at_validation() -> None:
    hosts = {"eutils.ncbi.nlm.nih.gov", "www.ebi.ac.uk", "clinicaltrials.gov", "api.platform.opentargets.org"}
    async with mock_http(source_router(fail_hosts=hosts), max_retries=0) as http:
        state = await run_research(WorkflowDeps(llm=FakeLLM(), http=http, model_name="fake"), "s6", QUESTION)
    assert state["agent_statuses"][AgentName.VALIDATION.value].status == ExecutionStatus.FAILED
    assert AgentName.SYNTHESIS.value not in state["agent_statuses"]
