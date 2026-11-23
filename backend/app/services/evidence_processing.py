"""Deterministic evidence processing: cross-source deduplication and data-quality flags.

This is the non-LLM half of the Evidence Validation agent. It never changes what a source said;
it only merges duplicate records and annotates metadata gaps and caveats.
"""

from __future__ import annotations

from collections.abc import Iterable

from app.models.evidence import EvidenceRecord, EvidenceType, QualityFlag, SourceName

# When the same article is found in several sources, prefer the richest canonical record.
_SOURCE_PRIORITY = {
    SourceName.PUBMED: 0,
    SourceName.EUROPE_PMC: 1,
    SourceName.CLINICAL_TRIALS: 0,
    SourceName.CHEMBL: 0,
    SourceName.OPEN_TARGETS: 0,
    SourceName.PUBCHEM: 0,
    SourceName.OPENALEX: 2,
}


def deduplicate(records: Iterable[EvidenceRecord]) -> tuple[list[EvidenceRecord], int]:
    """Merge records that share any stable identifier (DOI, PMID, PMCID, NCT, ChEMBL, Ensembl).

    Uses union-find so transitive matches merge (A shares a DOI with B, B shares a PMID with C).
    Returns (deduplicated records in first-seen order, number of records removed).
    """
    items = list(records)
    parent = list(range(len(items)))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    def union(a: int, b: int) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[max(ra, rb)] = min(ra, rb)

    seen: dict[str, int] = {}
    for idx, rec in enumerate(items):
        keys = rec.identifiers.keys()
        # Open Targets rows are disease-specific; key on the full record id instead of the bare gene.
        if rec.source_name == SourceName.OPEN_TARGETS:
            keys = [rec.record_id]
        for key in keys + [f"record:{rec.record_id}"]:
            if key in seen:
                union(seen[key], idx)
            else:
                seen[key] = idx

    groups: dict[int, list[EvidenceRecord]] = {}
    for idx, rec in enumerate(items):
        groups.setdefault(find(idx), []).append(rec)

    merged = [_merge(groups[root]) for root in sorted(groups)]
    return merged, len(items) - len(merged)


def _merge(group: list[EvidenceRecord]) -> EvidenceRecord:
    if len(group) == 1:
        return group[0].model_copy(deep=True)
    group = sorted(group, key=lambda r: _SOURCE_PRIORITY.get(r.source_name, 9))
    primary = group[0].model_copy(deep=True)
    for other in group[1:]:
        if other.source_name != primary.source_name and other.source_name not in primary.also_found_in:
            primary.also_found_in.append(other.source_name)
        # Fill gaps only; never overwrite what the canonical source reported.
        if not primary.summary and other.summary:
            primary.summary = other.summary
            primary.metadata["summary_from"] = other.source_name.value
        if not primary.publication_date and other.publication_date:
            primary.publication_date = other.publication_date
        if not primary.authors and other.authors:
            primary.authors = other.authors
        if not primary.journal and other.journal:
            primary.journal = other.journal
        for field in (
            "doi",
            "pmid",
            "pmcid",
            "nct_id",
            "chembl_id",
            "ensembl_id",
            "openalex_id",
            "pubchem_cid",
        ):
            if not getattr(primary.identifiers, field) and getattr(other.identifiers, field):
                setattr(primary.identifiers, field, getattr(other.identifiers, field))
        # Only replace an UNKNOWN type with a known one; known types reported by the canonical source stand.
        if primary.evidence_type == EvidenceType.UNKNOWN and other.evidence_type != EvidenceType.UNKNOWN:
            primary.evidence_type = other.evidence_type
        primary.publication_types = sorted(set(primary.publication_types) | set(other.publication_types))
        if other.metadata.get("is_open_access"):
            primary.metadata["is_open_access"] = True
        if other.metadata.get("cited_by_count") is not None:
            primary.metadata.setdefault("cited_by_count", other.metadata["cited_by_count"])
        # OpenAlex context (topics, author institutions) is kept alongside the canonical record.
        for key in ("topics", "institutions"):
            if other.metadata.get(key) and not primary.metadata.get(key):
                primary.metadata[key] = other.metadata[key]
    primary.metadata["merged_record_ids"] = [r.record_id for r in group]
    return primary


def assess_quality(record: EvidenceRecord) -> EvidenceRecord:
    """Attach deterministic data-quality flags. Returns a new record."""
    rec = record.model_copy(deep=True)
    flags: list[QualityFlag] = []
    md = rec.metadata

    if rec.category.value == "literature":
        if not rec.summary:
            flags.append(QualityFlag.MISSING_ABSTRACT)
        else:
            flags.append(QualityFlag.ABSTRACT_ONLY)
        if not rec.authors:
            flags.append(QualityFlag.MISSING_AUTHORS)
        if rec.evidence_type == EvidenceType.PREPRINT:
            flags.append(QualityFlag.NOT_PEER_REVIEWED)
        if any(p.lower() == "retracted publication" for p in rec.publication_types):
            flags.append(QualityFlag.RETRACTED)

    if rec.category.value in ("literature", "clinical_trial") and not rec.publication_date:
        flags.append(QualityFlag.MISSING_DATE)

    if rec.category.value == "clinical_trial":
        status = (md.get("overall_status") or "").upper()
        if status in {"TERMINATED", "WITHDRAWN", "SUSPENDED"}:
            flags.append(QualityFlag.TRIAL_STOPPED_EARLY)
        if status == "UNKNOWN" or not status:
            flags.append(QualityFlag.TRIAL_STATUS_UNKNOWN)
        if status == "COMPLETED" and not md.get("has_results"):
            flags.append(QualityFlag.TRIAL_NO_POSTED_RESULTS)

    if rec.category.value == "compound" and md.get("withdrawn"):
        flags.append(QualityFlag.COMPOUND_WITHDRAWN)

    rec.quality_flags = list(dict.fromkeys(flags))
    return rec


def process_evidence(records: Iterable[EvidenceRecord]) -> tuple[list[EvidenceRecord], int]:
    """Deduplicate then flag. Returns (validated records, duplicates removed)."""
    deduped, removed = deduplicate(records)
    return [assess_quality(r) for r in deduped], removed
