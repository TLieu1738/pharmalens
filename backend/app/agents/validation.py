"""Evidence Validation agent (deterministic).

Deduplicates across sources, attaches data-quality flags and computes an evidence profile. This step is
intentionally rule-based: identifier matching and metadata checks are more reliable and auditable in code
than in an LLM, and no numeric "confidence score" is invented.
"""

from collections import Counter
from dataclasses import dataclass, field
from typing import Any

from app.models.evidence import EvidenceRecord, QualityFlag
from app.services.evidence_processing import process_evidence
from app.services.record_checks import record_problems


@dataclass
class ValidationResult:
    records: list[EvidenceRecord]
    duplicates_removed: int
    profile: dict[str, Any]
    warnings: list[str] = field(default_factory=list)


def validate_evidence(records: list[EvidenceRecord]) -> ValidationResult:
    accepted: list[EvidenceRecord] = []
    rejected: list[dict[str, Any]] = []
    for record in records:
        problems = record_problems(record)
        if problems:
            rejected.append({"record_id": record.record_id, "problems": problems})
        else:
            accepted.append(record)
    validated, removed = process_evidence(accepted)
    by_type = Counter(r.evidence_type.value for r in validated)
    by_category = Counter(r.category.value for r in validated)
    by_source = Counter(r.source_name.value for r in validated)
    flags = Counter(f.value for r in validated for f in r.quality_flags)
    years = sorted(int(r.publication_date[:4]) for r in validated if r.publication_date)
    trial_status = Counter(
        r.metadata.get("status_label") or "Unknown" for r in validated if r.category.value == "clinical_trial"
    )

    warnings: list[str] = []
    if rejected:
        warnings.append(f"{len(rejected)} record(s) rejected: malformed identifiers or missing provenance.")
    if flags.get(QualityFlag.NOT_PEER_REVIEWED):
        warnings.append(f"{flags[QualityFlag.NOT_PEER_REVIEWED]} preprint(s) included — not peer reviewed.")
    if flags.get(QualityFlag.RETRACTED):
        warnings.append(
            f"{flags[QualityFlag.RETRACTED]} retracted publication(s) retrieved — treat with caution."
        )
    if flags.get(QualityFlag.TRIAL_STOPPED_EARLY):
        warnings.append(
            f"{flags[QualityFlag.TRIAL_STOPPED_EARLY]} trial(s) terminated, withdrawn or suspended."
        )
    if flags.get(QualityFlag.TRIAL_NO_POSTED_RESULTS):
        warnings.append(
            f"{flags[QualityFlag.TRIAL_NO_POSTED_RESULTS]} completed trial(s) have no results posted on ClinicalTrials.gov."
        )
    if flags.get(QualityFlag.MISSING_ABSTRACT):
        warnings.append(f"{flags[QualityFlag.MISSING_ABSTRACT]} publication(s) lack an abstract.")

    profile = {
        "total_records": len(validated),
        "duplicates_removed": removed,
        "by_evidence_type": dict(by_type),
        "by_category": dict(by_category),
        "by_source": dict(by_source),
        "quality_flags": dict(flags),
        "trial_status": dict(trial_status),
        "publication_year_range": [years[0], years[-1]] if years else None,
        "cross_source_matches": sum(1 for r in validated if r.also_found_in),
        "records_rejected": len(rejected),
        "rejected": rejected[:50],
    }
    return ValidationResult(records=validated, duplicates_removed=removed, profile=profile, warnings=warnings)
