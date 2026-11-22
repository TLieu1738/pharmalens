"""Manual smoke test against LIVE public APIs (not part of the unit-test suite).

Usage:  python -m scripts.smoke_sources "alzheimer amyloid tau"
"""

import asyncio
import sys
import time

from app.integrations.chembl import search_compounds
from app.integrations.clinical_trials import search_clinical_trials
from app.integrations.europe_pmc import search_europe_pmc
from app.integrations.http import SourceHttpClient
from app.integrations.open_targets import disease_targets
from app.integrations.pubmed import search_pubmed


async def main(query: str) -> None:
    async with SourceHttpClient() as http:
        jobs = {
            "pubmed": search_pubmed(http, f"{query} AND hasabstract", max_results=5),
            "europe_pmc": search_europe_pmc(http, query, max_results=5),
            "clinical_trials": search_clinical_trials(
                http, condition="Alzheimer Disease", term="amyloid", max_results=5
            ),
            "chembl": search_compounds(http, ["lecanemab", "donanemab"]),
            "open_targets": disease_targets(
                http, "Alzheimer disease", max_results=5, focus_targets=["MAPT", "APP"]
            ),
        }
        start = time.perf_counter()
        results = await asyncio.gather(*jobs.values(), return_exceptions=True)
        for name, res in zip(jobs, results, strict=True):
            if isinstance(res, BaseException):
                print(f"[FAIL] {name}: {res}")
                continue
            print(f"[ OK ] {name}: {len(res)} records")
            for r in res[:2]:
                print(f"       - {r.record_id} | {r.evidence_type} | {r.publication_date} | {r.title[:70]}")
        print(f"elapsed {time.perf_counter() - start:.1f}s")


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1] if len(sys.argv) > 1 else "alzheimer amyloid tau"))
