"""Literature agent: PubMed + Europe PMC for every protocol query, in parallel (deterministic retrieval)."""

import asyncio
import math

from app.agents.base import RetrievalResult, run_search
from app.integrations.europe_pmc import search_europe_pmc_paged
from app.integrations.http import SourceHttpClient
from app.integrations.pubmed import search_pubmed_paged
from app.models.evidence import SourceName
from app.models.research import ResearchPlan


async def retrieve_literature(
    http: SourceHttpClient,
    plan: ResearchPlan,
    *,
    per_source: int | None = None,
    ncbi_api_key: str | None = None,
) -> RetrievalResult:
    """Run each protocol query against each selected literature source.

    The protocol's per-source cap is split evenly across its queries; duplicates within a source are
    dropped here, and cross-source duplicates are merged later by the validation agent.
    """
    result = RetrievalResult()
    queries = plan.literature_queries
    cap = per_source or plan.max_results_per_source
    per_query = max(1, math.ceil(cap / len(queries)))
    jobs = []
    for query in queries:
        if SourceName.PUBMED in plan.sources:
            pubmed_query = f"({query}) AND hasabstract"
            jobs.append(
                run_search(
                    result,
                    SourceName.PUBMED.value,
                    search_pubmed_paged(
                        http,
                        pubmed_query,
                        max_results=per_query,
                        api_key=ncbi_api_key,
                        date_from=plan.date_from,
                        date_to=plan.date_to,
                    ),
                    query=pubmed_query,
                    requested=per_query,
                )
            )
        if SourceName.EUROPE_PMC in plan.sources:
            jobs.append(
                run_search(
                    result,
                    SourceName.EUROPE_PMC.value,
                    search_europe_pmc_paged(
                        http,
                        query,
                        max_results=per_query,
                        date_from=plan.date_from,
                        date_to=plan.date_to,
                        include_preprints=plan.include_preprints,
                    ),
                    query=query,
                    requested=per_query,
                )
            )
    seen: set[str] = set()
    for records in await asyncio.gather(*jobs):
        for record in records:
            if record.record_id not in seen:
                seen.add(record.record_id)
                result.records.append(record)
    if not plan.include_preprints:
        result.records = [r for r in result.records if r.evidence_type.value != "preprint"]
    result.message = (
        f"Retrieved {len(result.records)} publication records for {len(queries)} "
        f"{'query' if len(queries) == 1 else 'queries'}: {'; '.join(queries)}"
    )
    return result
