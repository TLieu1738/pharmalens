"""Test doubles: a fake LLM and a router that serves recorded fixtures for every source."""

from __future__ import annotations

from typing import Any, TypeVar

import httpx
from pydantic import BaseModel

from app.agents.llm import LLMError
from app.agents.planner import PlannerOutput
from app.models.evidence import SourceName
from app.models.report import Statement, StatementKind, SynthesisOutput
from tests.helpers import fixture_json, fixture_text

T = TypeVar("T", bound=BaseModel)

PLAN = PlannerOutput(
    disease_area="Alzheimer disease",
    biological_targets=["amyloid-beta", "tau"],
    target_gene_symbols=["APP", "MAPT"],
    compounds=["lecanemab"],
    concepts=["anti-amyloid antibodies"],
    objectives=["summarise evidence"],
    literature_query="(alzheimer disease) AND (amyloid beta OR tau)",
    clinical_condition="Alzheimer Disease",
    clinical_intervention_terms=["amyloid"],
    sources=list(SourceName),
    rationale="Search literature, trials, compounds and targets for amyloid and tau.",
)


def synthesis_output() -> SynthesisOutput:
    ok = Statement(
        text="APP is the top-ranked Open Targets association.",
        kind=StatementKind.FINDING,
        citations=["open_targets:MONDO_0004975:ENSG00000142192"],
    )
    review = Statement(
        text="A review addresses amyloid and tau PET use criteria.",
        kind=StatementKind.FINDING,
        citations=["pubmed:39776249", "pubmed:00000000"],
    )  # second id is fabricated
    unsupported = Statement(text="Drug X cures the disease.", kind=StatementKind.FINDING, citations=[])
    gap = Statement(text="Long-term outcomes remain unclear.", kind=StatementKind.GAP, citations=[])
    return SynthesisOutput(
        executive_summary=[ok, unsupported],
        biological_targets=[ok],
        compounds_and_interventions=[],
        literature_findings=[review],
        clinical_trial_landscape=[],
        evidence_strengths=[],
        evidence_limitations=[],
        research_gaps=[gap],
    )


class FakeLLM:
    def __init__(self, *, fail_on: type[BaseModel] | None = None) -> None:
        self.calls: list[str] = []
        self.prompts: list[str] = []
        self.fail_on = fail_on

    async def structured(
        self, *, system: str, prompt: str, output: type[T], effort: str = "medium", max_tokens: int = 16000
    ) -> T:
        self.calls.append(output.__name__)
        self.prompts.append(prompt)
        if self.fail_on is output:
            raise LLMError("simulated failure")
        if output is PlannerOutput:
            return PLAN  # type: ignore[return-value]
        if output is SynthesisOutput:
            return synthesis_output()  # type: ignore[return-value]
        raise AssertionError(f"unexpected schema {output}")


def source_router(*, fail_hosts: set[str] | None = None):
    """httpx MockTransport handler that serves fixtures for every integrated source."""
    fail_hosts = fail_hosts or set()

    def handler(request: httpx.Request) -> httpx.Response:
        host, path = request.url.host, request.url.path
        if host in fail_hosts:
            return httpx.Response(503)
        if host == "eutils.ncbi.nlm.nih.gov":
            if path.endswith("esearch.fcgi"):
                return httpx.Response(200, json=fixture_json("pubmed_esearch.json"))
            return httpx.Response(200, text=fixture_text("pubmed_efetch.xml"))
        if host == "www.ebi.ac.uk" and "europepmc" in path:
            return httpx.Response(200, json=fixture_json("europe_pmc_search.json"))
        if host == "www.ebi.ac.uk" and path.endswith("/molecule/search.json"):
            return httpx.Response(200, json=fixture_json("chembl_molecule_search.json"))
        if host == "www.ebi.ac.uk" and path.endswith("/mechanism.json"):
            return httpx.Response(200, json=fixture_json("chembl_mechanism.json"))
        if host == "clinicaltrials.gov":
            return httpx.Response(200, json=fixture_json("clinical_trials_studies.json"))
        if host == "api.platform.opentargets.org":
            body: Any = request.read().decode()
            name = "open_targets_search.json" if "DiseaseSearch" in body else "open_targets_associations.json"
            return httpx.Response(200, json=fixture_json(name))
        return httpx.Response(404)

    return handler
