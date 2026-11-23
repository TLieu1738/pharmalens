"""Normalised evidence records shared by every integration, agent and API response."""

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field, HttpUrl


class SourceName(StrEnum):
    PUBMED = "pubmed"
    EUROPE_PMC = "europe_pmc"
    CLINICAL_TRIALS = "clinicaltrials_gov"
    CHEMBL = "chembl"
    OPEN_TARGETS = "open_targets"


SOURCE_LABELS: dict[SourceName, str] = {
    SourceName.PUBMED: "PubMed",
    SourceName.EUROPE_PMC: "Europe PMC",
    SourceName.CLINICAL_TRIALS: "ClinicalTrials.gov",
    SourceName.CHEMBL: "ChEMBL",
    SourceName.OPEN_TARGETS: "Open Targets",
}


class EvidenceCategory(StrEnum):
    LITERATURE = "literature"
    CLINICAL_TRIAL = "clinical_trial"
    COMPOUND = "compound"
    TARGET = "target"


class EvidenceType(StrEnum):
    PRIMARY_RESEARCH = "primary_research"
    REVIEW = "review"
    PREPRINT = "preprint"
    CLINICAL_TRIAL = "clinical_trial"
    REGULATORY = "regulatory"
    DATABASE_RECORD = "database_record"
    UNKNOWN = "unknown"


class QualityFlag(StrEnum):
    """Deterministic data-quality flags. These describe metadata, not scientific merit."""

    MISSING_ABSTRACT = "missing_abstract"
    MISSING_DATE = "missing_date"
    MISSING_AUTHORS = "missing_authors"
    ABSTRACT_ONLY = "abstract_only"
    NOT_PEER_REVIEWED = "not_peer_reviewed"
    RETRACTED = "retracted"
    TRIAL_STOPPED_EARLY = "trial_stopped_early"
    TRIAL_NO_POSTED_RESULTS = "trial_no_posted_results"
    TRIAL_STATUS_UNKNOWN = "trial_status_unknown"
    COMPOUND_WITHDRAWN = "compound_withdrawn"


class Identifiers(BaseModel):
    """Stable cross-source identifiers used for deduplication."""

    doi: str | None = None
    pmid: str | None = None
    pmcid: str | None = None
    nct_id: str | None = None
    chembl_id: str | None = None
    ensembl_id: str | None = None

    def keys(self) -> list[str]:
        """Namespaced identifier keys, normalised for matching (e.g. 'doi:10.1/abc')."""
        out: list[str] = []
        for field, value in self.model_dump().items():
            if value:
                out.append(f"{field}:{str(value).strip().lower()}")
        return out


class Provenance(BaseModel):
    """Where a record came from. Set only by source parsers (see integrations/provenance.py)."""

    origin: str = "source_api"
    api_url: str = Field(description="Request that returns exactly this record from the source API.")
    payload_sha256: str = Field(pattern=r"^[0-9a-f]{64}$", description="Fingerprint of the raw source item.")
    parser: str


class EvidenceRecord(BaseModel):
    """One retrieved record, normalised across sources. Never constructed from LLM output."""

    record_id: str = Field(description="Stable key: '<source>:<identifier>'. Used for citations.")
    source_name: SourceName
    source_identifier: str
    category: EvidenceCategory
    evidence_type: EvidenceType
    title: str
    summary: str | None = Field(
        default=None, description="Abstract / brief summary as provided by the source."
    )
    source_url: HttpUrl
    publication_date: str | None = Field(
        default=None, description="ISO date, possibly partial (YYYY or YYYY-MM)."
    )
    retrieved_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    identifiers: Identifiers = Field(default_factory=Identifiers)
    authors: list[str] = Field(default_factory=list)
    journal: str | None = None
    publication_types: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    # None only for records stored before provenance tracking existed; new records always carry it.
    provenance: Provenance | None = None
    # Populated by the validation step
    quality_flags: list[QualityFlag] = Field(default_factory=list)
    also_found_in: list[SourceName] = Field(default_factory=list)
