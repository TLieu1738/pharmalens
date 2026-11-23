"""OpenAlex Works API: scholarly works with citation counts, author institutions and topics.

Docs: https://docs.openalex.org/api-entities/works
OpenAlex indexes far more than biomedicine and covers the same papers as PubMed and Europe PMC; records are
deduplicated against them by DOI / PMID / PMCID in the validation step. Abstracts are rebuilt from OpenAlex's
inverted index exactly as provided (no text is generated). An API key is optional; without one requests share a
small daily budget per IP address, and a refusal is reported as a source failure, not an empty result.
"""

from __future__ import annotations

import logging
from typing import Any

from app.integrations._parsing import clean_text, date_from_text, truncate
from app.integrations.http import SourceError, SourceHttpClient
from app.integrations.literature_types import classify_publication
from app.integrations.paging import PAGE_SIZE, SearchPage, as_int
from app.integrations.provenance import make_provenance
from app.models.evidence import EvidenceCategory, EvidenceRecord, Identifiers, SourceName

logger = logging.getLogger(__name__)

WORKS_URL = "https://api.openalex.org/works"
SOURCE = SourceName.OPENALEX.value
SELECT = (
    "id,doi,ids,title,display_name,publication_date,type,authorships,primary_location,"
    "cited_by_count,open_access,primary_topic,topics,abstract_inverted_index,is_retracted"
)
_TYPE_LABELS = {"article": "Journal Article", "review": "Review", "preprint": "Preprint"}


def build_filter(*, date_from: int | None, date_to: int | None, include_preprints: bool) -> str | None:
    parts = []
    if date_from:
        parts.append(f"from_publication_date:{date_from}-01-01")
    if date_to:
        parts.append(f"to_publication_date:{date_to}-12-31")
    if not include_preprints:
        parts.append("type:!preprint")
    return ",".join(parts) or None


async def search_openalex_paged(
    http: SourceHttpClient,
    query: str,
    *,
    max_results: int = 15,
    date_from: int | None = None,
    date_to: int | None = None,
    include_preprints: bool = True,
    api_key: str | None = None,
    page_size: int = PAGE_SIZE,
) -> SearchPage:
    """Relevance-ranked ("best matches first") search, paged with `cursor` until `max_results` records."""
    flt = build_filter(date_from=date_from, date_to=date_to, include_preprints=include_preprints)
    page = SearchPage(query=query + (f" [filter: {flt}]" if flt else ""))
    cursor = "*"
    while len(page.records) < max_results:
        size = min(page_size, max_results - len(page.records))
        params: dict[str, Any] = {"search": query, "per-page": size, "cursor": cursor, "select": SELECT}
        if flt:
            params["filter"] = flt
        if api_key:
            params["api_key"] = api_key
        data = await http.get_json(SOURCE, WORKS_URL, params)
        batch = parse_openalex(data)
        raw_count = len(data["results"])
        page.pages += 1
        page.total_available = as_int((data.get("meta") or {}).get("count"))
        page.records.extend(batch)
        next_cursor = (data.get("meta") or {}).get("next_cursor")
        if raw_count < size or not next_cursor or next_cursor == cursor:
            break
        cursor = next_cursor
    page.records = page.records[:max_results]
    return page


def parse_openalex(data: Any) -> list[EvidenceRecord]:
    if not isinstance(data, dict) or not isinstance(data.get("results"), list):
        raise SourceError(SOURCE, "unexpected works response shape")
    records = []
    for item in data["results"]:
        try:
            record = _parse_work(item)
        except Exception:
            logger.warning("openalex_parse_skip reason=malformed_work", exc_info=True)
            continue
        if record:
            records.append(record)
    return records


def abstract_from_index(index: Any) -> str | None:
    """Rebuild an abstract from OpenAlex's {word: [positions]} inverted index."""
    if not isinstance(index, dict) or not index:
        return None
    positions: dict[int, str] = {}
    for word, places in index.items():
        for pos in places or []:
            if isinstance(pos, int):
                positions[pos] = word
    return " ".join(positions[i] for i in sorted(positions)) or None


def _tail(url: Any, prefix: str = "/") -> str | None:
    if not isinstance(url, str) or not url:
        return None
    return url.rstrip("/").rsplit(prefix, 1)[-1] or None


def _parse_work(item: dict[str, Any]) -> EvidenceRecord | None:
    work_id = _tail(item.get("id"))
    title = clean_text(item.get("title") or item.get("display_name"))
    if not work_id or not title:
        return None
    ids = item.get("ids") or {}
    doi = item.get("doi") or ids.get("doi")
    doi = doi.split("doi.org/", 1)[-1] if isinstance(doi, str) else None
    pmid = _tail(ids.get("pmid"))
    pmcid = _tail(ids.get("pmcid"))

    work_type = (item.get("type") or "").lower()
    pub_types = [_TYPE_LABELS.get(work_type, work_type.title())] if work_type else []
    if item.get("is_retracted"):
        pub_types.append("Retracted Publication")

    authorships = item.get("authorships") or []
    authors = [
        (a.get("author") or {}).get("display_name")
        for a in authorships
        if (a.get("author") or {}).get("display_name")
    ]
    institutions = list(
        dict.fromkeys(
            inst.get("display_name")
            for a in authorships
            for inst in a.get("institutions") or []
            if inst.get("display_name")
        )
    )
    topics = [t.get("display_name") for t in item.get("topics") or [] if t.get("display_name")][:3]
    source = (item.get("primary_location") or {}).get("source") or {}

    return EvidenceRecord(
        record_id=f"openalex:{work_id}",
        source_name=SourceName.OPENALEX,
        source_identifier=work_id,
        category=EvidenceCategory.LITERATURE,
        evidence_type=classify_publication(pub_types, is_preprint=work_type == "preprint"),
        title=title,
        summary=truncate(clean_text(abstract_from_index(item.get("abstract_inverted_index")))),
        source_url=f"https://openalex.org/{work_id}",
        provenance=make_provenance("openalex", f"{WORKS_URL}/{work_id}", item),
        publication_date=date_from_text(item.get("publication_date")),
        identifiers=Identifiers(doi=doi, pmid=pmid, pmcid=pmcid, openalex_id=work_id),
        authors=authors[:25],
        journal=source.get("display_name"),
        publication_types=pub_types,
        metadata={
            "cited_by_count": item.get("cited_by_count"),
            "is_open_access": bool((item.get("open_access") or {}).get("is_oa")),
            "institutions": institutions[:10],
            "topics": topics,
            "openalex_type": work_type or None,
        },
    )
