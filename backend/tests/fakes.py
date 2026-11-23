"""Test doubles: a fake LLM and a router that serves recorded fixtures for every source."""

from __future__ import annotations

from typing import Any, TypeVar

import httpx
from pydantic import BaseModel

from app.agents.llm import LLMError
from app.agents.planner import PlannerOutput
from app.agents.verification import CitationVerdict, ClaimVerdict, VerificationOutput
from app.models.evidence import SourceName
from app.models.report import ClaimDraft, StatementKind, SynthesisOutput
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
    objective="Summarise evidence on amyloid-beta and tau approaches in Alzheimer disease.",
    key_questions=["Which compounds target amyloid-beta?", "What trials are registered?"],
    additional_literature_queries=[],
    inclusion_criteria=["Human studies and registered trials"],
    exclusion_criteria=["Unrelated dementias"],
    date_from=None,
    date_to=None,
    intended_outputs=["Cited evidence briefing"],
    known_limitations=["Top-ranked records only"],
)


def synthesis_output() -> SynthesisOutput:
    ok = ClaimDraft(
        limitations=[],
        text="APP is the top-ranked Open Targets association.",
        kind=StatementKind.FINDING,
        citations=["open_targets:MONDO_0004975:ENSG00000142192"],
    )
    review = ClaimDraft(
        limitations=[],
        text="A review addresses amyloid and tau PET use criteria.",
        kind=StatementKind.FINDING,
        citations=["pubmed:39776249", "pubmed:00000000"],
    )  # second id is fabricated
    unsupported = ClaimDraft(
        limitations=[], text="Drug X cures the disease.", kind=StatementKind.FINDING, citations=[]
    )
    gap = ClaimDraft(
        limitations=[], text="Long-term outcomes remain unclear.", kind=StatementKind.GAP, citations=[]
    )
    return SynthesisOutput(
        executive_summary=[ok, unsupported],
        biological_targets=[ok],
        compounds_and_interventions=[],
        literature_findings=[review],
        clinical_trial_landscape=[],
        evidence_strengths=[],
        evidence_limitations=[],
        conflicting_evidence=[],
        research_gaps=[gap],
        conclusions=[ok],
    )


class FakeLLM:
    """Planner, synthesis and claim-verification stand-in.

    `verdict` decides the semantic check: a function (claim text, record_id) -> relevance; default "supports".
    `synthesis` overrides the drafted report.
    """

    def __init__(
        self,
        *,
        fail_on: type[BaseModel] | None = None,
        verdict: Any = None,
        synthesis: SynthesisOutput | None = None,
    ) -> None:
        self.calls: list[str] = []
        self.prompts: list[str] = []
        self.fail_on = fail_on
        self.verdict = verdict or (lambda text, rid: "supports")
        self.synthesis = synthesis

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
            return self.synthesis or synthesis_output()  # type: ignore[return-value]
        if output is VerificationOutput:
            return self._verify(prompt)  # type: ignore[return-value]
        raise AssertionError(f"unexpected schema {output}")


def _overall(relevances: list[str]) -> str:
    if "contradicts" in relevances:
        return "contradicted"
    if "supports" in relevances:
        return "supported"
    if "partially_supports" in relevances:
        return "partially_supported"
    return "unsupported"


def _verify_claims(self: FakeLLM, prompt: str) -> VerificationOutput:
    import json

    claims = prompt.split("<claims>\n", 1)[1].split("\n</claims>", 1)[0].splitlines()
    verdicts = []
    for line in claims:
        c = json.loads(line)
        cites = [CitationVerdict(record_id=r, relevance=self.verdict(c["text"], r)) for r in c["citations"]]
        verdicts.append(
            ClaimVerdict(
                claim_id=c["claim_id"],
                overall=_overall([v.relevance for v in cites]),
                citations=cites,
                note="fake verdict",
            )
        )
    return VerificationOutput(verdicts=verdicts)


FakeLLM._verify = _verify_claims  # type: ignore[attr-defined]


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
