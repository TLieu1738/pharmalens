"""Deterministic checks that a record is a well-formed, traceable copy of a real source record.

Applied by the Evidence Validation agent before anything is persisted. A record that fails is rejected
(and reported), never repaired or guessed at.
"""

from __future__ import annotations

import re
from urllib.parse import urlparse

from app.models.evidence import EvidenceRecord, SourceName

# Source identifier formats as issued by each database.
IDENTIFIER_PATTERNS: dict[SourceName, re.Pattern[str]] = {
    SourceName.PUBMED: re.compile(r"^\d{1,9}$"),
    SourceName.EUROPE_PMC: re.compile(r"^[A-Z]{2,4}:[A-Za-z0-9._/-]{1,40}$"),
    SourceName.CLINICAL_TRIALS: re.compile(r"^NCT\d{8}$"),
    SourceName.CHEMBL: re.compile(r"^CHEMBL\d{1,9}$"),
    SourceName.OPEN_TARGETS: re.compile(r"^[A-Za-z]+_\d+:ENSG\d{11}$"),
    SourceName.PUBCHEM: re.compile(r"^\d{1,10}$"),
    SourceName.OPENALEX: re.compile(r"^W\d{1,12}$"),
}

# Each source's records must link back to that source's own domain.
SOURCE_HOSTS: dict[SourceName, str] = {
    SourceName.PUBMED: "pubmed.ncbi.nlm.nih.gov",
    SourceName.EUROPE_PMC: "europepmc.org",
    SourceName.CLINICAL_TRIALS: "clinicaltrials.gov",
    SourceName.CHEMBL: "www.ebi.ac.uk",
    SourceName.OPEN_TARGETS: "platform.opentargets.org",
    SourceName.PUBCHEM: "pubchem.ncbi.nlm.nih.gov",
    SourceName.OPENALEX: "openalex.org",
}

PROVENANCE_HOSTS: dict[SourceName, str] = {
    SourceName.PUBMED: "eutils.ncbi.nlm.nih.gov",
    SourceName.EUROPE_PMC: "www.ebi.ac.uk",
    SourceName.CLINICAL_TRIALS: "clinicaltrials.gov",
    SourceName.CHEMBL: "www.ebi.ac.uk",
    SourceName.OPEN_TARGETS: "api.platform.opentargets.org",
    SourceName.PUBCHEM: "pubchem.ncbi.nlm.nih.gov",
    SourceName.OPENALEX: "api.openalex.org",
}


def record_problems(record: EvidenceRecord) -> list[str]:
    """Why a record is not a valid, traceable source record (empty list = valid)."""
    problems: list[str] = []
    source = record.source_name
    if not IDENTIFIER_PATTERNS[source].match(record.source_identifier):
        problems.append(f"identifier '{record.source_identifier}' is not a valid {source.value} identifier")
    if record.record_id != f"{source.value}:{record.source_identifier}":
        problems.append("record_id does not match source and identifier")
    if urlparse(str(record.source_url)).hostname != SOURCE_HOSTS[source]:
        problems.append(f"source URL is not on {SOURCE_HOSTS[source]}")
    if not record.title.strip():
        problems.append("missing title")
    if record.provenance is None:
        problems.append("missing provenance (not produced by a source parser)")
    elif urlparse(record.provenance.api_url).hostname != PROVENANCE_HOSTS[source]:
        problems.append("provenance URL does not point at the source API")
    return problems
