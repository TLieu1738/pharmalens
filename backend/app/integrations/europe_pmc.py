"""Europe PMC REST search API (core result type includes abstracts).

Docs: https://europepmc.org/RestfulWebService
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

SEARCH_URL = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
SOURCE = SourceName.EUROPE_PMC.value


async def search_europe_pmc(
    http: SourceHttpClient, query: str, *, max_results: int = 15
) -> list[EvidenceRecord]:
    return (await search_europe_pmc_paged(http, query, max_results=max_results)).records


def build_query(query: str, *, date_from: int | None, date_to: int | None, include_preprints: bool) -> str:
    """Add the protocol's filters using Europe PMC query syntax. Unfiltered queries pass through unchanged."""
    if not (date_from or date_to or not include_preprints):
        return query
    full = f"({query})"
    if date_from or date_to:
        full += f" AND (PUB_YEAR:[{date_from or 1800} TO {date_to or 3000}])"
    if not include_preprints:
        full += " NOT (SRC:PPR)"
    return full


async def search_europe_pmc_paged(
    http: SourceHttpClient,
    query: str,
    *,
    max_results: int = 15,
    date_from: int | None = None,
    date_to: int | None = None,
    include_preprints: bool = True,
    page_size: int = PAGE_SIZE,
) -> SearchPage:
    """Relevance-ranked search, paged with `cursorMark` until `max_results` records."""
    full = build_query(query, date_from=date_from, date_to=date_to, include_preprints=include_preprints)
    page = SearchPage(query=full)
    cursor = "*"
    while len(page.records) < max_results:
        size = min(page_size, max_results - len(page.records))
        params = {
            "query": full,
            "format": "json",
            "resultType": "core",
            "pageSize": size,
            "cursorMark": cursor,
        }
        data = await http.get_json(SOURCE, SEARCH_URL, params)
        batch = parse_europe_pmc(data)
        raw_count = len(data["resultList"]["result"])
        page.pages += 1
        page.total_available = as_int(data.get("hitCount")) if isinstance(data, dict) else None
        page.records.extend(batch)
        next_cursor = data.get("nextCursorMark") if isinstance(data, dict) else None
        if raw_count < size or not next_cursor or next_cursor == cursor:
            break
        cursor = next_cursor
    page.records = page.records[:max_results]
    return page


def parse_europe_pmc(data: Any) -> list[EvidenceRecord]:
    try:
        results = data["resultList"]["result"]
    except (KeyError, TypeError) as exc:
        raise SourceError(SOURCE, "unexpected search response shape") from exc
    records = []
    for item in results:
        try:
            record = _parse_result(item)
        except Exception:
            logger.warning("europe_pmc_parse_skip reason=malformed_result", exc_info=True)
            continue
        if record:
            records.append(record)
    return records


def _parse_result(item: dict[str, Any]) -> EvidenceRecord | None:
    source_db = item.get("source")  # MED, PMC, PPR (preprints), AGR, ...
    ext_id = item.get("id")
    title = clean_text(item.get("title"))
    if not source_db or not ext_id or not title:
        return None

    pub_types = (item.get("pubTypeList") or {}).get("pubType") or []
    if isinstance(pub_types, str):
        pub_types = [pub_types]
    is_preprint = source_db == "PPR"

    authors = [
        a.get("fullName") or a.get("collectiveName")
        for a in (item.get("authorList") or {}).get("author", [])
        if a.get("fullName") or a.get("collectiveName")
    ]
    journal = ((item.get("journalInfo") or {}).get("journal") or {}).get("title")
    if is_preprint and not journal:
        journal = (item.get("bookOrReportDetails") or {}).get("publisher")

    return EvidenceRecord(
        record_id=f"europe_pmc:{source_db}:{ext_id}",
        source_name=SourceName.EUROPE_PMC,
        source_identifier=f"{source_db}:{ext_id}",
        category=EvidenceCategory.LITERATURE,
        evidence_type=classify_publication(pub_types, is_preprint=is_preprint),
        title=title,
        summary=truncate(clean_text(item.get("abstractText"))),
        source_url=f"https://europepmc.org/article/{source_db}/{ext_id}",
        provenance=make_provenance(
            "europe_pmc",
            f"{SEARCH_URL}?query=EXT_ID:{ext_id}%20AND%20SRC:{source_db}&format=json&resultType=core",
            item,
        ),
        publication_date=date_from_text(item.get("firstPublicationDate"))
        or date_from_text(item.get("pubYear")),
        identifiers=Identifiers(
            pmid=item.get("pmid"),
            pmcid=item.get("pmcid"),
            doi=item.get("doi"),
        ),
        authors=authors,
        journal=journal,
        publication_types=pub_types,
        metadata={
            "europe_pmc_source": source_db,
            "is_open_access": item.get("isOpenAccess") == "Y",
            "cited_by_count": item.get("citedByCount"),
            "content_scope": "abstract_only",
        },
    )
