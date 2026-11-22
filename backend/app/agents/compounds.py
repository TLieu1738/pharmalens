"""Compound agent: ChEMBL lookups for compounds named in the plan and found in retrieved trials.

Runs after the Clinical agent so that investigational products from real trial registrations can be
looked up, not only the names the planner suggested. Only exact name/synonym matches are kept.
"""

import re
from collections import Counter

from app.agents.base import RetrievalResult, run_source
from app.integrations.chembl import search_compounds
from app.integrations.http import SourceHttpClient
from app.models.evidence import EvidenceRecord, SourceName
from app.models.research import ResearchPlan

_EXCLUDE = re.compile(r"placebo|saline|vehicle|standard of care|usual care|control", re.I)
_DRUG_TYPES = {"Drug", "Biological"}


_DOSE = re.compile(r"\s+\d[\d.,]*\s*(mg|mcg|µg|ug|g|ml|mL|mg/kg|iu|IU|%)(\b|/).*$", re.I)


def normalise_intervention_name(raw: str) -> str:
    """Strip dosing and parenthetical detail but keep code names intact ('AV-1980R', 'LY3202626')."""
    name = re.split(r"[(\[,;/]| - ", raw)[0]
    return _DOSE.sub("", name).strip()


def unique_compound_queries(names: list[str]) -> list[str]:
    """Order-preserving dedupe that also drops arm labels repeating an earlier name
    (e.g. 'lecanemab treatment group' after 'lecanemab')."""
    kept: list[str] = []
    for raw in names:
        name = raw.strip()
        words = set(name.lower().split())
        if name and not any(k.lower() == name.lower() or k.lower() in words for k in kept):
            kept.append(name)
    return kept


def trial_intervention_names(trials: list[EvidenceRecord], limit: int = 5) -> list[str]:
    """Most frequent drug/biological intervention names across retrieved trials, normalised."""
    counts: Counter[str] = Counter()
    for trial in trials:
        for item in trial.metadata.get("interventions", []):
            if item.get("type") not in _DRUG_TYPES or not item.get("name"):
                continue
            name = normalise_intervention_name(item["name"])
            if 3 <= len(name) <= 40 and not _EXCLUDE.search(name):
                counts[name.lower()] += 1
    return [name for name, _ in counts.most_common(limit)]


async def retrieve_compounds(
    http: SourceHttpClient, plan: ResearchPlan, trials: list[EvidenceRecord], *, max_names: int = 8
) -> RetrievalResult:
    result = RetrievalResult()
    if SourceName.CHEMBL not in plan.sources:
        result.message = "ChEMBL not selected by the planner."
        return result
    queries = unique_compound_queries(plan.compounds + trial_intervention_names(trials))[:max_names]
    if not queries:
        result.message = "No compound names identified to look up."
        return result
    found = await run_source(result, SourceName.CHEMBL.value, search_compounds(http, queries, per_name=2))
    exact = [r for r in found if r.metadata.get("exact_name_match")]
    result.records = exact
    matched = {r.metadata.get("query", "").lower() for r in exact}
    unmatched = [q for q in queries if q.lower() not in matched]
    if result.sources:  # reflect the post-filter count
        result.sources[-1].record_count = len(exact)
    result.message = f"Looked up {len(queries)} compounds; {len(exact)} exact ChEMBL matches."
    if unmatched:
        result.warnings.append(f"No exact ChEMBL record found for: {', '.join(unmatched)}")
    return result
