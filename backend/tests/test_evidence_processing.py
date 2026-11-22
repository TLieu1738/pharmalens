from app.models.evidence import (
    EvidenceCategory,
    EvidenceRecord,
    EvidenceType,
    Identifiers,
    QualityFlag,
    SourceName,
)
from app.services.evidence_processing import deduplicate, process_evidence


def lit(record_id: str, source: SourceName, **kw: object) -> EvidenceRecord:
    base: dict[str, object] = dict(
        record_id=record_id,
        source_name=source,
        source_identifier=record_id.split(":")[-1],
        category=EvidenceCategory.LITERATURE,
        evidence_type=EvidenceType.PRIMARY_RESEARCH,
        title="T",
        source_url="https://example.org/x",
        authors=["A B"],
        publication_date="2024",
        summary="abstract",
    )
    base.update(kw)
    return EvidenceRecord.model_validate(base)


def test_dedup_merges_by_doi_case_insensitively_and_prefers_pubmed() -> None:
    epmc = lit(
        "europe_pmc:MED:1",
        SourceName.EUROPE_PMC,
        identifiers=Identifiers(doi="10.1/ABC"),
        metadata={"is_open_access": True},
    )
    pm = lit("pubmed:1", SourceName.PUBMED, identifiers=Identifiers(doi="10.1/abc", pmid="1"), summary=None)
    merged, removed = deduplicate([epmc, pm])
    assert removed == 1
    (rec,) = merged
    assert rec.source_name == SourceName.PUBMED
    assert rec.also_found_in == [SourceName.EUROPE_PMC]
    assert rec.summary == "abstract"  # gap filled from Europe PMC
    assert rec.metadata["summary_from"] == "europe_pmc"
    assert rec.metadata["is_open_access"] is True


def test_dedup_is_transitive_across_identifiers() -> None:
    a = lit("pubmed:1", SourceName.PUBMED, identifiers=Identifiers(pmid="1", doi="10.1/a"))
    b = lit("europe_pmc:MED:1", SourceName.EUROPE_PMC, identifiers=Identifiers(pmid="1", pmcid="PMC9"))
    c = lit("europe_pmc:PMC:PMC9", SourceName.EUROPE_PMC, identifiers=Identifiers(pmcid="PMC9"))
    merged, removed = deduplicate([a, b, c])
    assert len(merged) == 1 and removed == 2
    assert merged[0].identifiers.pmcid == "PMC9"


def test_distinct_records_are_kept_and_order_preserved() -> None:
    a = lit("pubmed:1", SourceName.PUBMED, identifiers=Identifiers(pmid="1"))
    b = lit("pubmed:2", SourceName.PUBMED, identifiers=Identifiers(pmid="2"))
    merged, removed = deduplicate([b, a])
    assert removed == 0 and [r.record_id for r in merged] == ["pubmed:2", "pubmed:1"]


def test_quality_flags_for_literature() -> None:
    rec = lit(
        "europe_pmc:PPR:1",
        SourceName.EUROPE_PMC,
        evidence_type=EvidenceType.PREPRINT,
        summary=None,
        authors=[],
        publication_date=None,
        publication_types=["Retracted Publication"],
    )
    (out,), _ = process_evidence([rec])
    assert set(out.quality_flags) == {
        QualityFlag.MISSING_ABSTRACT,
        QualityFlag.MISSING_AUTHORS,
        QualityFlag.NOT_PEER_REVIEWED,
        QualityFlag.RETRACTED,
        QualityFlag.MISSING_DATE,
    }


def test_quality_flags_for_trials_and_compounds() -> None:
    def trial(nct: str, status: str, has_results: bool) -> EvidenceRecord:
        return EvidenceRecord(
            record_id=f"clinicaltrials_gov:{nct}",
            source_name=SourceName.CLINICAL_TRIALS,
            source_identifier=nct,
            category=EvidenceCategory.CLINICAL_TRIAL,
            evidence_type=EvidenceType.CLINICAL_TRIAL,
            title="t",
            source_url=f"https://clinicaltrials.gov/study/{nct}",
            publication_date="2020",
            identifiers=Identifiers(nct_id=nct),
            metadata={"overall_status": status, "has_results": has_results},
        )

    compound = EvidenceRecord(
        record_id="chembl:C1",
        source_name=SourceName.CHEMBL,
        source_identifier="C1",
        category=EvidenceCategory.COMPOUND,
        evidence_type=EvidenceType.DATABASE_RECORD,
        title="c",
        source_url="https://www.ebi.ac.uk/chembl/explore/compound/C1",
        metadata={"withdrawn": True},
    )
    out, _ = process_evidence(
        [trial("NCT1", "TERMINATED", True), trial("NCT2", "COMPLETED", False), compound]
    )
    assert out[0].quality_flags == [QualityFlag.TRIAL_STOPPED_EARLY]
    assert out[1].quality_flags == [QualityFlag.TRIAL_NO_POSTED_RESULTS]
    assert out[2].quality_flags == [QualityFlag.COMPOUND_WITHDRAWN]


def test_processing_does_not_mutate_inputs() -> None:
    rec = lit("pubmed:1", SourceName.PUBMED, summary=None)
    process_evidence([rec])
    assert rec.quality_flags == []
