"""Literature agent: PubMed + Europe PMC in parallel (deterministic retrieval)."""

import asyncio

from app.agents.base import RetrievalResult, run_source
from app.integrations.europe_pmc import search_europe_pmc
from app.integrations.http import SourceHttpClient
from app.integrations.pubmed import search_pubmed
from app.models.evidence import SourceName
from app.models.research import ResearchPlan


async def retrieve_literature(
    http: SourceHttpClient, plan: ResearchPlan, *, per_source: int = 15, ncbi_api_key: str | None = None
) -> RetrievalResult:
    result = RetrievalResult()
    jobs = []
    if SourceName.PUBMED in plan.sources:
        jobs.append(
            run_source(
                result,
                SourceName.PUBMED.value,
                search_pubmed(
                    http,
                    f"({plan.literature_query}) AND hasabstract",
                    max_results=per_source,
                    api_key=ncbi_api_key,
                ),
            )
        )
    if SourceName.EUROPE_PMC in plan.sources:
        jobs.append(
            run_source(
                result,
                SourceName.EUROPE_PMC.value,
                search_europe_pmc(http, plan.literature_query, max_results=per_source),
            )
        )
    for records in await asyncio.gather(*jobs):
        result.records.extend(records)
    result.message = f"Retrieved {len(result.records)} publication records for: {plan.literature_query}"
    return result
