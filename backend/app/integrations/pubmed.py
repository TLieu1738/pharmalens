"""PubMed via NCBI E-utilities (ESearch + EFetch XML).

Docs: https://www.ncbi.nlm.nih.gov/books/NBK25501/
Without an API key NCBI allows 3 requests/second; with NCBI_API_KEY, 10/second.
"""

from __future__ import annotations

import logging
import xml.etree.ElementTree as ET

from app.integrations._parsing import clean_text, date_from_text, normalise_date, truncate
from app.integrations.http import SourceError, SourceHttpClient
from app.integrations.literature_types import classify_publication
from app.models.evidence import EvidenceCategory, EvidenceRecord, Identifiers, SourceName

logger = logging.getLogger(__name__)

BASE_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
SOURCE = SourceName.PUBMED.value


async def search_pubmed(
    http: SourceHttpClient, query: str, *, max_results: int = 15, api_key: str | None = None
) -> list[EvidenceRecord]:
    params: dict[str, str | int] = {
        "db": "pubmed",
        "term": query,
        "retmax": max_results,
        "retmode": "json",
        "sort": "relevance",
        "tool": "pharmalens",
    }
    if api_key:
        params["api_key"] = api_key
    data = await http.get_json(SOURCE, f"{BASE_URL}/esearch.fcgi", params)
    try:
        ids: list[str] = data["esearchresult"]["idlist"]
    except (KeyError, TypeError) as exc:
        raise SourceError(SOURCE, "unexpected ESearch response shape") from exc
    if not ids:
        return []

    fetch_params: dict[str, str | int] = {
        "db": "pubmed",
        "id": ",".join(ids),
        "retmode": "xml",
        "tool": "pharmalens",
    }
    if api_key:
        fetch_params["api_key"] = api_key
    xml_text = await http.get_text(SOURCE, f"{BASE_URL}/efetch.fcgi", fetch_params)
    records = parse_pubmed_xml(xml_text)
    # Preserve relevance order from ESearch
    order = {pmid: i for i, pmid in enumerate(ids)}
    return sorted(records, key=lambda r: order.get(r.source_identifier, len(order)))


def parse_pubmed_xml(xml_text: str) -> list[EvidenceRecord]:
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as exc:
        raise SourceError(SOURCE, "invalid EFetch XML") from exc

    records: list[EvidenceRecord] = []
    for article in root.findall("PubmedArticle"):
        try:
            record = _parse_article(article)
        except Exception:  # one malformed article must not discard the batch
            logger.warning("pubmed_parse_skip reason=malformed_article", exc_info=True)
            continue
        if record:
            records.append(record)
    return records


def _text(el: ET.Element | None) -> str | None:
    """Full text content of an element including nested markup (e.g. <i>, <sup>)."""
    if el is None:
        return None
    return clean_text("".join(el.itertext()))


def _parse_article(article: ET.Element) -> EvidenceRecord | None:
    citation = article.find("MedlineCitation")
    art = citation.find("Article") if citation is not None else None
    if citation is None or art is None:
        return None
    pmid = citation.findtext("PMID")
    title = _text(art.find("ArticleTitle"))
    if not pmid or not title:
        return None

    abstract_parts = []
    for part in art.findall("Abstract/AbstractText"):
        text = _text(part)
        if text:
            label = part.get("Label")
            abstract_parts.append(f"{label}: {text}" if label else text)
    abstract = truncate(" ".join(abstract_parts)) if abstract_parts else None

    pub_date_el = art.find("Journal/JournalIssue/PubDate")
    pub_date = None
    if pub_date_el is not None:
        pub_date = normalise_date(
            pub_date_el.findtext("Year"), pub_date_el.findtext("Month"), pub_date_el.findtext("Day")
        ) or date_from_text(pub_date_el.findtext("MedlineDate"))
    if pub_date is None:
        art_date = art.find("ArticleDate")
        if art_date is not None:
            pub_date = normalise_date(
                art_date.findtext("Year"), art_date.findtext("Month"), art_date.findtext("Day")
            )

    authors = []
    for author in art.findall("AuthorList/Author"):
        last, initials = author.findtext("LastName"), author.findtext("Initials")
        collective = author.findtext("CollectiveName")
        if last:
            authors.append(f"{last} {initials}".strip() if initials else last)
        elif collective:
            authors.append(collective)

    ids = {
        (a.get("IdType") or "").lower(): (a.text or "").strip()
        for a in article.findall("PubmedData/ArticleIdList/ArticleId")
    }
    pub_types = [t.text for t in art.findall("PublicationTypeList/PublicationType") if t.text]
    mesh = [d.text for d in citation.findall("MeshHeadingList/MeshHeading/DescriptorName") if d.text]

    return EvidenceRecord(
        record_id=f"pubmed:{pmid}",
        source_name=SourceName.PUBMED,
        source_identifier=pmid,
        category=EvidenceCategory.LITERATURE,
        evidence_type=classify_publication(pub_types),
        title=title,
        summary=abstract,
        source_url=f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
        publication_date=pub_date,
        identifiers=Identifiers(pmid=pmid, doi=ids.get("doi") or None, pmcid=ids.get("pmc") or None),
        authors=authors,
        journal=clean_text(art.findtext("Journal/Title")),
        publication_types=pub_types,
        metadata={"mesh_terms": mesh[:15], "content_scope": "abstract_only"},
    )
