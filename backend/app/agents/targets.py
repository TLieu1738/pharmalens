"""Biological Target agent: Open Targets disease-target associations (deterministic retrieval)."""

from app.agents.base import RetrievalResult, run_source
from app.integrations.http import SourceHttpClient
from app.integrations.open_targets import disease_targets
from app.models.evidence import SourceName
from app.models.research import ResearchPlan


async def retrieve_targets(
    http: SourceHttpClient, plan: ResearchPlan, *, max_results: int | None = None
) -> RetrievalResult:
    result = RetrievalResult()
    if SourceName.OPEN_TARGETS not in plan.sources or not plan.disease_area:
        result.message = "No disease area identified; target associations skipped."
        return result
    result.records = await run_source(
        result,
        SourceName.OPEN_TARGETS.value,
        disease_targets(
            http,
            plan.disease_area,
            max_results=min(max_results or plan.max_results_per_source, 50),
            focus_targets=plan.target_gene_symbols + plan.biological_targets,
        ),
    )
    if result.records:
        disease = result.records[0].metadata.get("disease_name")
        focus = [
            r.metadata["target_symbol"] for r in result.records if r.metadata.get("matches_question_focus")
        ]
        result.message = f"Top {len(result.records)} targets associated with {disease}" + (
            f"; question focus found: {', '.join(focus)}" if focus else ""
        )
    return result
