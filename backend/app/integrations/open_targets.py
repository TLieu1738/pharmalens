"""Open Targets Platform GraphQL API: disease → associated targets.

Docs: https://platform-docs.opentargets.org/data-access/graphql-api
An association score summarises the strength of aggregated evidence linking a target to a disease.
It is NOT evidence of causation or of therapeutic validity.
"""

from __future__ import annotations

from typing import Any

from app.integrations.http import SourceError, SourceHttpClient
from app.models.evidence import EvidenceCategory, EvidenceRecord, EvidenceType, Identifiers, SourceName

GRAPHQL_URL = "https://api.platform.opentargets.org/api/v4/graphql"
SOURCE = SourceName.OPEN_TARGETS.value

_SEARCH_QUERY = """
query DiseaseSearch($q: String!) {
  search(queryString: $q, entityNames: ["disease"], page: {index: 0, size: 1}) { hits { id name } }
}"""

_ASSOC_QUERY = """
query DiseaseTargets($id: String!, $size: Int!) {
  disease(efoId: $id) {
    id name
    associatedTargets(page: {index: 0, size: $size}) {
      count
      rows { score target { id approvedSymbol approvedName } datatypeScores { id score } }
    }
  }
}"""


async def disease_targets(
    http: SourceHttpClient, disease: str, *, max_results: int = 15, focus_targets: list[str] | None = None
) -> list[EvidenceRecord]:
    search = await http.post_json(SOURCE, GRAPHQL_URL, {"query": _SEARCH_QUERY, "variables": {"q": disease}})
    hits = _data(search).get("search", {}).get("hits") or []
    if not hits:
        return []
    disease_id = hits[0]["id"]
    assoc = await http.post_json(
        SOURCE, GRAPHQL_URL, {"query": _ASSOC_QUERY, "variables": {"id": disease_id, "size": max_results}}
    )
    return parse_associations(assoc, focus_targets=focus_targets or [])


def _data(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict) or payload.get("errors") or not isinstance(payload.get("data"), dict):
        raise SourceError(SOURCE, "GraphQL error or unexpected response")
    return payload["data"]


def parse_associations(payload: Any, *, focus_targets: list[str]) -> list[EvidenceRecord]:
    disease = _data(payload).get("disease")
    if not disease:
        return []
    focus = {t.strip().lower() for t in focus_targets}
    records = []
    for rank, row in enumerate((disease.get("associatedTargets") or {}).get("rows") or [], start=1):
        target = row.get("target") or {}
        ensembl_id, symbol = target.get("id"), target.get("approvedSymbol")
        if not ensembl_id or not symbol:
            continue
        name = target.get("approvedName") or symbol
        datatypes = {d["id"]: round(d["score"], 3) for d in row.get("datatypeScores") or [] if "id" in d}
        evidence_kinds = ", ".join(
            k.replace("_", " ") for k, v in sorted(datatypes.items(), key=lambda kv: -kv[1])
        )
        records.append(
            EvidenceRecord(
                record_id=f"open_targets:{disease['id']}:{ensembl_id}",
                source_name=SourceName.OPEN_TARGETS,
                source_identifier=f"{disease['id']}:{ensembl_id}",
                category=EvidenceCategory.TARGET,
                evidence_type=EvidenceType.DATABASE_RECORD,
                title=f"{symbol} — {name}",
                summary=(
                    f"Open Targets lists {symbol} as associated with {disease['name']} "
                    f"(rank {rank} by overall association score). Evidence types contributing: "
                    f"{evidence_kinds or 'not specified'}. Association does not establish causation."
                ),
                source_url=f"https://platform.opentargets.org/evidence/{ensembl_id}/{disease['id']}",
                identifiers=Identifiers(ensembl_id=ensembl_id),
                metadata={
                    "disease_id": disease["id"],
                    "disease_name": disease["name"],
                    "target_symbol": symbol,
                    "target_name": name,
                    "association_score": round(row.get("score") or 0, 3),
                    "association_rank": rank,
                    "datatype_scores": datatypes,
                    "matches_question_focus": symbol.lower() in focus or name.lower() in focus,
                },
            )
        )
    return records
