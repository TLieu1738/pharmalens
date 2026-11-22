"""Clinical Intelligence agent: ClinicalTrials.gov (deterministic retrieval)."""

from app.agents.base import RetrievalResult, run_source
from app.integrations.clinical_trials import search_clinical_trials
from app.integrations.http import SourceHttpClient
from app.models.evidence import SourceName
from app.models.research import ResearchPlan

MAX_TRIAL_TERMS = 10


def _or_terms(terms: list[str]) -> str | None:
    cleaned = list(dict.fromkeys(t.strip() for t in terms if t.strip()))[:MAX_TRIAL_TERMS]
    if not cleaned:
        return None
    return " OR ".join(f'"{t}"' if " " in t else t for t in cleaned)


def trial_search_terms(plan: ResearchPlan) -> list[str]:
    """Named compounds first (registrations list drug names, rarely class phrases), then class terms.

    Falls back to biological targets when the planner named neither.
    """
    terms = plan.compounds + plan.clinical_intervention_terms
    return terms or plan.biological_targets[:3]


async def retrieve_trials(
    http: SourceHttpClient, plan: ResearchPlan, *, max_results: int = 20
) -> RetrievalResult:
    result = RetrievalResult()
    if SourceName.CLINICAL_TRIALS not in plan.sources:
        result.message = "ClinicalTrials.gov not selected by the planner."
        return result
    condition = plan.clinical_condition or plan.disease_area
    term = _or_terms(trial_search_terms(plan))
    if not condition and not term:
        result.message = "No condition or intervention terms to search."
        return result
    result.records = await run_source(
        result,
        SourceName.CLINICAL_TRIALS.value,
        search_clinical_trials(http, condition=condition, term=term, max_results=max_results),
    )
    result.message = f"Retrieved {len(result.records)} registered studies (condition: {condition or 'any'}; terms: {term or 'none'})"
    return result
