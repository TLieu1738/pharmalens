"""ChEMBL web services: molecule search, mechanism of action and mechanism targets.

Docs: https://www.ebi.ac.uk/chembl/api/data/docs
Only public descriptive data is captured: identifiers (including the standard InChIKey, used to find the same
substance in PubChem), development phase, mechanism, and the gene symbols ChEMBL records for each mechanism
target (used to connect compounds to Open Targets targets). No process or synthesis information is captured.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from app.integrations.http import SourceError, SourceHttpClient
from app.integrations.provenance import make_provenance
from app.models.evidence import EvidenceCategory, EvidenceRecord, EvidenceType, Identifiers, SourceName

logger = logging.getLogger(__name__)

BASE_URL = "https://www.ebi.ac.uk/chembl/api/data"
SOURCE = SourceName.CHEMBL.value

# ChEMBL max_phase semantics: highest development phase reached for ANY indication, anywhere.
PHASE_LABELS = {
    4.0: "Approved (in at least one indication/region)",
    3.0: "Phase 3",
    2.0: "Phase 2",
    1.0: "Phase 1",
    0.5: "Early Phase 1",
    -1.0: "Clinical phase unknown",
}


async def search_compounds(
    http: SourceHttpClient, names: list[str], *, per_name: int = 2
) -> list[EvidenceRecord]:
    """Look up each compound name; failures for individual names are logged, not fatal."""
    results = await asyncio.gather(*(_search_one(http, n, per_name) for n in names), return_exceptions=True)
    records: dict[str, EvidenceRecord] = {}
    errors = 0
    for name, result in zip(names, results, strict=True):
        if isinstance(result, BaseException):
            errors += 1
            logger.warning("chembl_lookup_failed name=%s error=%s", name, result)
            continue
        for rec in result:
            records.setdefault(rec.record_id, rec)
    if names and errors == len(names):
        raise SourceError(SOURCE, "all compound lookups failed")
    return list(records.values())


async def _search_one(http: SourceHttpClient, name: str, limit: int) -> list[EvidenceRecord]:
    data = await http.get_json(SOURCE, f"{BASE_URL}/molecule/search.json", {"q": name, "limit": limit})
    molecules = parse_molecules(data, query=name)
    # Enrich with mechanism of action (best-effort)
    mech_results = await asyncio.gather(
        *(
            http.get_json(
                SOURCE, f"{BASE_URL}/mechanism.json", {"molecule_chembl_id": m.source_identifier, "limit": 5}
            )
            for m in molecules
        ),
        return_exceptions=True,
    )
    for record, mech in zip(molecules, mech_results, strict=True):
        if isinstance(mech, BaseException):
            continue
        record.metadata["mechanisms"] = parse_mechanisms(mech)
    await _annotate_targets(http, molecules)
    return molecules


async def _annotate_targets(http: SourceHttpClient, molecules: list[EvidenceRecord]) -> None:
    """Add ChEMBL's own target name and gene symbols to each mechanism (best-effort, one call per target)."""
    target_ids = list(
        dict.fromkeys(
            m["target_chembl_id"]
            for rec in molecules
            for m in rec.metadata.get("mechanisms", [])
            if m.get("target_chembl_id")
        )
    )
    if not target_ids:
        return
    results = await asyncio.gather(
        *(http.get_json(SOURCE, f"{BASE_URL}/target/{tid}.json") for tid in target_ids),
        return_exceptions=True,
    )
    targets = {
        tid: parse_target(data)
        for tid, data in zip(target_ids, results, strict=True)
        if not isinstance(data, BaseException)
    }
    for rec in molecules:
        for mech in rec.metadata.get("mechanisms", []):
            info = targets.get(mech.get("target_chembl_id") or "")
            if info:
                mech.update(info)


def parse_target(data: Any) -> dict[str, Any]:
    """Target name, type, organism and the gene symbols ChEMBL lists for its components."""
    if not isinstance(data, dict) or not data.get("target_chembl_id"):
        return {}
    symbols: list[str] = []
    for component in data.get("target_components") or []:
        for syn in component.get("target_component_synonyms") or []:
            if syn.get("syn_type") == "GENE_SYMBOL" and syn.get("component_synonym"):
                symbols.append(syn["component_synonym"].strip())
    return {
        "target_name": data.get("pref_name"),
        "target_type": data.get("target_type"),
        "target_organism": data.get("organism"),
        "target_gene_symbols": list(dict.fromkeys(symbols))[:10],
    }


def parse_molecules(data: Any, *, query: str) -> list[EvidenceRecord]:
    if not isinstance(data, dict) or not isinstance(data.get("molecules"), list):
        raise SourceError(SOURCE, "unexpected molecule search response shape")
    records = []
    for mol in data["molecules"]:
        chembl_id = mol.get("molecule_chembl_id")
        if not chembl_id:
            continue
        name = mol.get("pref_name") or chembl_id
        max_phase = _to_float(mol.get("max_phase"))
        all_synonyms = {
            s.get("molecule_synonym") for s in mol.get("molecule_synonyms") or [] if s.get("molecule_synonym")
        }
        exact_match = query.strip().lower() in {n.lower() for n in all_synonyms | {name}}
        synonyms = sorted(all_synonyms)[:8]
        summary_bits = [f"{mol.get('molecule_type') or 'Molecule'} in ChEMBL."]
        if max_phase is not None:
            summary_bits.append(
                f"Highest development phase recorded by ChEMBL: {PHASE_LABELS.get(max_phase, max_phase)}."
            )
        if mol.get("first_approval"):
            summary_bits.append(f"First approval year recorded: {mol['first_approval']}.")
        records.append(
            EvidenceRecord(
                record_id=f"chembl:{chembl_id}",
                source_name=SourceName.CHEMBL,
                source_identifier=chembl_id,
                category=EvidenceCategory.COMPOUND,
                evidence_type=EvidenceType.DATABASE_RECORD,
                title=name.title() if name.isupper() else name,
                summary=" ".join(summary_bits),
                source_url=f"https://www.ebi.ac.uk/chembl/explore/compound/{chembl_id}",
                provenance=make_provenance(
                    "chembl", f"https://www.ebi.ac.uk/chembl/api/data/molecule/{chembl_id}.json", mol
                ),
                identifiers=Identifiers(chembl_id=chembl_id),
                metadata={
                    "query": query,
                    "molecule_type": mol.get("molecule_type"),
                    "max_phase": max_phase,
                    "max_phase_label": PHASE_LABELS.get(max_phase) if max_phase is not None else None,
                    "first_approval": mol.get("first_approval"),
                    "withdrawn": bool(mol.get("withdrawn_flag")),
                    "black_box_warning": mol.get("black_box_warning") == 1,
                    "synonyms": synonyms,
                    "mechanisms": [],
                    "match_score": mol.get("score"),
                    "exact_name_match": exact_match,
                    # Standard InChIKey for small molecules; None for biologics such as antibodies.
                    "inchi_key": (mol.get("molecule_structures") or {}).get("standard_inchi_key"),
                },
            )
        )
    return records


def parse_mechanisms(data: Any) -> list[dict[str, Any]]:
    out = []
    for m in (data or {}).get("mechanisms") or []:
        if m.get("mechanism_of_action"):
            out.append(
                {
                    "mechanism_of_action": m["mechanism_of_action"],
                    "action_type": m.get("action_type"),
                    "target_chembl_id": m.get("target_chembl_id"),
                }
            )
    return out


def _to_float(value: Any) -> float | None:
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None
