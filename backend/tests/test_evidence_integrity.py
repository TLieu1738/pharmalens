"""Evidence integrity: provenance, identifier validation, claim verification and the publication gate.

All sources and the LLM are mocked; every record below is parsed from responses recorded from the real APIs.
"""

from __future__ import annotations

from typing import Any

import httpx
import pytest

from app.agents.llm import LLMError
from app.agents.synthesis import _record_digest
from app.agents.validation import validate_evidence
from app.agents.verification import VerificationOutput, verify_report
from app.integrations.chembl import parse_molecules
from app.integrations.clinical_trials import parse_studies
from app.integrations.open_targets import parse_associations
from app.integrations.pubmed import parse_pubmed_xml
from app.models.evidence import EvidenceRecord
from app.models.report import (
    ClaimDraft,
    ReportNotPublishableError,
    StatementKind,
    SynthesisOutput,
    ValidationStatus,
)
from app.services.repository import InMemorySessionRepository
from app.services.supabase_repository import SupabaseSessionRepository
from tests.fakes import FakeLLM
from tests.helpers import fixture_json, fixture_text

PUBMED = "pubmed:39776249"
APP_TARGET = "open_targets:MONDO_0004975:ENSG00000142192"
TRIAL = "clinicaltrials_gov:NCT06325527"  # enrolment 1872, not yet recruiting, no results
LECANEMAB = "chembl:CHEMBL3833321"  # max phase 4, first approval 2023


def records() -> list[EvidenceRecord]:
    return [
        *parse_pubmed_xml(fixture_text("pubmed_efetch.xml")),
        *parse_associations(fixture_json("open_targets_associations.json"), focus_targets=[]),
        *parse_studies(fixture_json("clinical_trials_studies.json")),
        *parse_molecules(fixture_json("chembl_molecule_search.json"), query="lecanemab"),
    ]


def claim(text: str, kind: StatementKind, *cites: str) -> ClaimDraft:
    return ClaimDraft(text=text, kind=kind, citations=list(cites), limitations=["Abstract only."])


def draft(**sections: list[ClaimDraft]) -> SynthesisOutput:
    empty: dict[str, Any] = {
        k: []
        for k in (
            "executive_summary",
            "biological_targets",
            "compounds_and_interventions",
            "literature_findings",
            "clinical_trial_landscape",
            "evidence_strengths",
            "evidence_limitations",
            "conflicting_evidence",
            "research_gaps",
            "conclusions",
        )
    }
    return SynthesisOutput(**{**empty, **sections})


async def verify(
    d: SynthesisOutput,
    llm: Any = None,
    persisted: set[str] | None = None,
    recs: list[EvidenceRecord] | None = None,
):
    recs = recs or records()
    return await verify_report(
        llm if llm is not None else FakeLLM(),
        d,
        recs,
        persisted_ids=persisted,
        context_numbers=[],
        question="q",
        scope="s",
        model="m",
        records_provided=len(recs),
    )


def published(report) -> list:  # type: ignore[no-untyped-def]
    return [st for s in report.sections for st in s.statements]


# --------------------------------------------------------------------------------------- provenance
def test_every_parsed_record_carries_provenance() -> None:
    for r in records():
        assert r.provenance is not None and r.provenance.origin == "source_api"
        assert len(r.provenance.payload_sha256) == 64
        assert r.source_identifier in r.provenance.api_url or "graphql" in r.provenance.api_url


def test_llm_output_cannot_create_evidence_records() -> None:
    # The synthesis schema only carries text and record-ID strings: there is no way to emit a record.
    fields = SynthesisOutput.model_json_schema()["$defs"]["ClaimDraft"]["properties"]
    assert set(fields) == {"text", "kind", "citations", "limitations"}


# ------------------------------------------------------------------------- malformed / fabricated records
def test_validation_rejects_malformed_and_untraceable_records() -> None:
    good = records()[0]
    fabricated = good.model_copy(update={"record_id": "pubmed:12AB", "source_identifier": "12AB"})
    no_provenance = good.model_copy(
        update={"record_id": "pubmed:1", "source_identifier": "1", "provenance": None}
    )
    wrong_host = good.model_copy(
        update={"record_id": "pubmed:2", "source_identifier": "2", "source_url": "https://evil.example/2"}
    )
    result = validate_evidence([good, fabricated, no_provenance, wrong_host])
    assert [r.record_id for r in result.records] == [good.record_id]
    reasons = {x["record_id"]: " ".join(x["problems"]) for x in result.profile["rejected"]}
    assert "not a valid pubmed identifier" in reasons["pubmed:12AB"]
    assert "missing provenance" in reasons["pubmed:1"]
    assert "source URL" in reasons["pubmed:2"]
    assert any("rejected" in w for w in result.warnings)


def test_malformed_source_items_are_skipped_not_guessed() -> None:
    data = fixture_json("clinical_trials_studies.json")
    data["studies"].append({"protocolSection": {"identificationModule": {}}})  # type: ignore[index]
    assert len(parse_studies(data)) == 2


# ---------------------------------------------------------------------------------- citation existence
async def test_fabricated_identifier_removes_the_claim() -> None:
    report = await verify(
        draft(
            literature_findings=[claim("A trial showed benefit.", StatementKind.FINDING, "pubmed:99999999")]
        )
    )
    assert published(report) == []
    removed = report.integrity.removed_statements[0]
    assert removed.reason == "cited only unknown record IDs" and removed.citations == ["pubmed:99999999"]


async def test_invalid_citation_is_dropped_but_supported_claim_kept() -> None:
    report = await verify(
        draft(
            biological_targets=[
                claim(
                    "APP is associated with Alzheimer disease.",
                    StatementKind.FINDING,
                    APP_TARGET,
                    "pubmed:00000000",
                )
            ]
        )
    )
    st = published(report)[0]
    assert st.citations == [APP_TARGET] and st.validation_status == ValidationStatus.SUPPORTED
    assert report.integrity.invalid_citations == ["pubmed:00000000"]


async def test_cross_session_citation_is_rejected() -> None:
    # The record exists (e.g. in another user's session) but was not persisted for this session.
    persisted = {r.record_id for r in records()} - {APP_TARGET}
    report = await verify(
        draft(
            biological_targets=[
                claim("APP is associated with Alzheimer disease.", StatementKind.FINDING, APP_TARGET)
            ]
        ),
        persisted=persisted,
    )
    assert (
        published(report) == []
        and report.integrity.removed_statements[0].reason == "cited only unknown record IDs"
    )


# --------------------------------------------------------------------------------- semantic support
async def test_valid_but_irrelevant_citation_is_not_treated_as_support() -> None:
    llm = FakeLLM(verdict=lambda text, rid: "irrelevant" if rid == PUBMED else "supports")
    mixed = claim("APP is associated with Alzheimer disease.", StatementKind.FINDING, APP_TARGET, PUBMED)
    only_irrelevant = claim("Lecanemab removes amyloid plaques.", StatementKind.FINDING, PUBMED)
    report = await verify(draft(literature_findings=[mixed, only_irrelevant]), llm=llm)
    [kept] = published(report)
    assert kept.citations == [APP_TARGET]  # the irrelevant (but real) citation was dropped
    assert {s.record_id: s.verdict for s in kept.support} == {APP_TARGET: "supports"}
    assert report.integrity.removed_statements[0].text.startswith("Lecanemab removes")
    assert report.integrity.removed_statements[0].status == "unsupported"


async def test_contradicted_claim_is_removed_and_marked() -> None:
    llm = FakeLLM(verdict=lambda text, rid: "contradicts")
    report = await verify(
        draft(
            literature_findings=[
                claim("APP is unrelated to Alzheimer disease.", StatementKind.FINDING, APP_TARGET)
            ]
        ),
        llm=llm,
    )
    assert published(report) == []
    assert report.integrity.removed_statements[0].status == "contradicted"
    assert report.integrity.status_counts["contradicted"] == 1


async def test_partially_supported_claim_is_published_with_caveat() -> None:
    llm = FakeLLM(verdict=lambda text, rid: "partially_supports")
    report = await verify(
        draft(
            literature_findings=[
                claim("APP is the main driver of Alzheimer disease.", StatementKind.FINDING, APP_TARGET)
            ]
        ),
        llm=llm,
    )
    [st] = published(report)
    assert st.validation_status == ValidationStatus.PARTIALLY_SUPPORTED and st.validation_notes


async def test_unsupported_interpretation_becomes_a_labelled_hypothesis() -> None:
    llm = FakeLLM(verdict=lambda text, rid: "irrelevant")
    report = await verify(
        draft(
            conclusions=[
                claim("Targeting APP may be the best strategy.", StatementKind.INTERPRETATION, APP_TARGET)
            ]
        ),
        llm=llm,
    )
    [st] = published(report)
    assert st.kind == StatementKind.HYPOTHESIS and st.validation_status == ValidationStatus.NOT_APPLICABLE
    assert report.integrity.relabelled and report.integrity.relabelled[0].status == "relabelled"


async def test_hypotheses_and_gaps_are_kept_and_labelled() -> None:
    report = await verify(
        draft(
            research_gaps=[
                claim("Long-term outcomes remain unclear.", StatementKind.GAP),
                claim("Combination therapy might help.", StatementKind.HYPOTHESIS),
            ]
        )
    )
    assert [st.validation_status for st in published(report)] == [ValidationStatus.NOT_APPLICABLE] * 2


async def test_semantic_check_outage_is_visible_not_silent() -> None:
    report = await verify(
        draft(
            biological_targets=[
                claim("APP is associated with Alzheimer disease.", StatementKind.FINDING, APP_TARGET)
            ]
        ),
        llm=FakeLLM(fail_on=VerificationOutput),
    )
    [st] = published(report)
    assert report.integrity.semantic_check == "unavailable"
    assert st.validation_status == ValidationStatus.NOT_VERIFIED and st.validation_notes


# ------------------------------------------------------------------------------ numbers and clinical data
async def test_invented_participant_count_is_rejected_real_one_kept() -> None:
    invented = claim("The trial enrolled 4,200 participants.", StatementKind.FINDING, TRIAL)
    real = claim("The trial plans to enrol 1,872 participants.", StatementKind.FINDING, TRIAL)
    report = await verify(draft(clinical_trial_landscape=[invented, real]))
    assert [st.text for st in published(report)] == [real.text]
    assert "4200" in report.integrity.removed_statements[0].reason


async def test_years_from_source_dates_are_accepted() -> None:
    pub = next(r for r in records() if r.record_id == PUBMED)
    year = (pub.publication_date or "")[:4]
    assert year and "-" in (pub.publication_date or "")  # a full date such as 2025-01-08
    report = await verify(
        draft(
            literature_findings=[
                claim(f"A {year} review covers PET use criteria.", StatementKind.FINDING, PUBMED)
            ]
        )
    )
    assert len(published(report)) == 1


async def test_missing_clinical_outcomes_are_not_inferred_from_registration() -> None:
    efficacy = claim(
        "Treatment slowed cognitive decline in this trial.", StatementKind.CLINICAL_OUTCOME, TRIAL
    )
    status_only = claim("The trial is not yet recruiting.", StatementKind.FINDING, TRIAL)
    report = await verify(draft(clinical_trial_landscape=[efficacy, status_only]))
    assert [st.text for st in published(report)] == [status_only.text]
    assert "outcome results were not retrieved" in report.integrity.removed_statements[0].reason
    trial = next(r for r in records() if r.record_id == TRIAL)
    assert _record_digest(trial)["outcome_results"] == "not retrieved (registry entry only)"


async def test_missing_drug_prices_cannot_be_stated() -> None:
    report = await verify(
        draft(
            compounds_and_interventions=[
                claim("Lecanemab costs £2,480 per patient per year.", StatementKind.FINDING, LECANEMAB)
            ]
        )
    )
    assert published(report) == []
    assert "no pricing data" in report.integrity.removed_statements[0].reason


async def test_approval_claims_are_checked_against_chembl_phase() -> None:
    approved = claim("Lecanemab is approved, first in 2023.", StatementKind.FINDING, LECANEMAB)
    report = await verify(draft(compounds_and_interventions=[approved]))
    assert published(report)[0].validation_status == ValidationStatus.SUPPORTED  # max phase 4, approval 2023

    phase3 = [
        r.model_copy(update={"metadata": {**r.metadata, "max_phase": 3.0}}) if r.record_id == LECANEMAB else r
        for r in records()
    ]
    report = await verify(
        draft(
            compounds_and_interventions=[claim("Lecanemab is approved.", StatementKind.FINDING, LECANEMAB)]
        ),
        recs=phase3,
    )
    assert published(report) == [] and report.integrity.removed_statements[0].status == "contradicted"


async def test_comparison_needs_two_sources() -> None:
    report = await verify(
        draft(
            literature_findings=[
                claim("APP ranks above other targets.", StatementKind.COMPARATIVE, APP_TARGET)
            ]
        )
    )
    [st] = published(report)
    assert st.validation_status == ValidationStatus.PARTIALLY_SUPPORTED
    assert "fewer than two" in " ".join(st.validation_notes)


# ----------------------------------------------------------------------------------- publication gate
async def test_repositories_refuse_unverified_reports() -> None:
    report = await verify(
        draft(
            biological_targets=[
                claim("APP is associated with Alzheimer disease.", StatementKind.FINDING, APP_TARGET)
            ]
        )
    )
    unverified = report.model_copy(
        update={"integrity": report.integrity.model_copy(update={"validated": False})}
    )
    smuggled = report.model_copy(deep=True)
    next(sec for sec in smuggled.sections if sec.statements).statements[
        0
    ].validation_status = ValidationStatus.UNSUPPORTED

    repo = InMemorySessionRepository()
    sid = await repo.create_session("A question about amyloid", "u1", demo_mode=False)
    for bad in (unverified, smuggled):
        with pytest.raises(ReportNotPublishableError):
            await repo.complete(sid, bad, {}, [])
    await repo.complete(sid, report, {}, [])  # the verified report goes through
    assert (await repo.get_status(sid)).value == "completed"  # type: ignore[union-attr]

    calls: list[str] = []
    client = httpx.AsyncClient(
        base_url="https://x.supabase.co/rest/v1",
        transport=httpx.MockTransport(lambda req: calls.append(str(req.url)) or httpx.Response(201, json=[])),
    )
    from app.config import Settings

    supa = SupabaseSessionRepository(
        Settings(
            _env_file=None, supabase_url="https://x.supabase.co", supabase_service_role_key="sb_secret_x"
        ),
        client,
    )
    with pytest.raises(ReportNotPublishableError):
        await supa.complete("s", unverified, {}, [])
    assert calls == []  # nothing was written


async def test_workflow_cannot_publish_without_verification_node() -> None:
    from app.graph.workflow import WorkflowDeps, build_workflow
    from tests.helpers import mock_http

    async with mock_http(lambda r: httpx.Response(404)) as http:
        _, execution = build_workflow(WorkflowDeps(llm=FakeLLM(), http=http, model_name="m"))
    nodes = set(execution.get_graph().nodes)
    assert {"synthesis", "verification"} <= nodes
    edges = {(e.source, e.target) for e in execution.get_graph().edges}
    assert ("synthesis", "__end__") in edges and ("synthesis", "verification") in edges
    assert ("verification", "__end__") in edges


async def test_llm_failure_in_synthesis_does_not_fabricate_a_report() -> None:
    from app.graph.workflow import WorkflowDeps, run_research
    from tests.fakes import source_router
    from tests.helpers import mock_http

    async with mock_http(source_router()) as http:
        state = await run_research(
            WorkflowDeps(llm=FakeLLM(fail_on=SynthesisOutput), http=http, model_name="m"), "s", "q"
        )
    assert state.get("report") is None and state["errors"]


def test_llm_error_type_is_exported() -> None:
    assert issubclass(LLMError, Exception)
