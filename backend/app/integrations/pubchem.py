"""PubChem PUG REST: chemical identifiers for compounds already found in ChEMBL.

Docs: https://pubchem.ncbi.nlm.nih.gov/docs/pug-rest
Lookups are by the standard InChIKey that ChEMBL reports, so a PubChem record is only linked to a ChEMBL compound
when both databases describe the same structure; names are never fuzzy-matched. Biologics (antibodies etc.)
have no InChIKey in ChEMBL and are skipped. Only descriptive identifiers and properties are captured
(CID, formula, molecular weight, InChIKey, IUPAC name, SMILES); no synthesis or process information.
"""

from __future__ import annotations

import asyncio
import logging
import re
from typing import Any

from app.integrations.http import SourceError, SourceHttpClient
from app.integrations.provenance import make_provenance
from app.models.evidence import EvidenceCategory, EvidenceRecord, EvidenceType, Identifiers, SourceName

logger = logging.getLogger(__name__)

BASE_URL = "https://pubchem.ncbi.nlm.nih.gov/rest/pug"
SOURCE = SourceName.PUBCHEM.value
PROPERTIES = "Title,MolecularFormula,MolecularWeight,InChIKey,IUPACName,SMILES"
_INCHIKEY = re.compile(r"^[A-Z]{14}-[A-Z]{10}-[A-Z]$")


def property_url(inchikey: str) -> str:
    return f"{BASE_URL}/compound/inchikey/{inchikey}/property/{PROPERTIES}/JSON"


async def lookup_by_inchikey(http: SourceHttpClient, compounds: list[EvidenceRecord]) -> list[EvidenceRecord]:
    """One PubChem record per ChEMBL compound whose InChIKey PubChem knows. Not-found keys are skipped.

    Raises SourceError only if every lookup failed for a reason other than "not found".
    """
    pairs = [
        (rec, rec.metadata["inchi_key"])
        for rec in compounds
        if isinstance(rec.metadata.get("inchi_key"), str) and _INCHIKEY.match(rec.metadata["inchi_key"])
    ]
    if not pairs:
        return []
    results = await asyncio.gather(
        *(http.get_json(SOURCE, property_url(key)) for _, key in pairs), return_exceptions=True
    )
    records: dict[str, EvidenceRecord] = {}
    failures = 0
    for (chembl_rec, key), data in zip(pairs, results, strict=True):
        if isinstance(data, SourceError) and data.message == "HTTP 404":
            continue  # PubChem has no compound with this structure
        if isinstance(data, BaseException):
            failures += 1
            logger.warning("pubchem_lookup_failed chembl_id=%s error=%s", chembl_rec.source_identifier, data)
            continue
        record = parse_properties(data, inchikey=key, chembl_id=chembl_rec.source_identifier)
        if record:
            records.setdefault(record.record_id, record)
    if failures == len(pairs):
        raise SourceError(SOURCE, "all PubChem lookups failed")
    return list(records.values())


def parse_properties(data: Any, *, inchikey: str, chembl_id: str) -> EvidenceRecord | None:
    try:
        props = data["PropertyTable"]["Properties"]
    except (KeyError, TypeError) as exc:
        raise SourceError(SOURCE, "unexpected property response shape") from exc
    # PubChem can return several CIDs for one key (e.g. salts); the first is its canonical match.
    item = next((p for p in props if p.get("CID") and p.get("InChIKey") == inchikey), None)
    if item is None:
        return None
    cid = str(item["CID"])
    title = item.get("Title") or item.get("IUPACName") or f"CID {cid}"
    formula = item.get("MolecularFormula")
    weight = item.get("MolecularWeight")
    bits = ["Compound record in PubChem, matched to ChEMBL " + chembl_id + " by standard InChIKey."]
    if formula:
        bits.append(f"Molecular formula {formula}.")
    if weight:
        bits.append(f"Molecular weight {weight} g/mol.")
    return EvidenceRecord(
        record_id=f"pubchem:{cid}",
        source_name=SourceName.PUBCHEM,
        source_identifier=cid,
        category=EvidenceCategory.COMPOUND,
        evidence_type=EvidenceType.DATABASE_RECORD,
        title=title,
        summary=" ".join(bits),
        source_url=f"https://pubchem.ncbi.nlm.nih.gov/compound/{cid}",
        provenance=make_provenance("pubchem", property_url(inchikey), item),
        identifiers=Identifiers(pubchem_cid=cid),
        metadata={
            "cid": cid,
            "molecular_formula": formula,
            "molecular_weight": weight,
            "inchi_key": item.get("InChIKey"),
            "iupac_name": item.get("IUPACName"),
            "smiles": item.get("SMILES"),
            "linked_chembl_id": chembl_id,
            "match_method": "standard InChIKey",
        },
    )
