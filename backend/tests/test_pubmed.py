import httpx
import pytest

from app.integrations.http import SourceError
from app.integrations.pubmed import parse_pubmed_xml, search_pubmed
from app.models.evidence import EvidenceCategory, EvidenceType, SourceName
from tests.helpers import fixture_json, fixture_text, mock_http


def test_parse_real_efetch_fixture() -> None:
    records = parse_pubmed_xml(fixture_text("pubmed_efetch.xml"))
    assert [r.source_identifier for r in records] == ["39776249", "27025652"]
    first = records[0]
    assert first.source_name == SourceName.PUBMED
    assert first.category == EvidenceCategory.LITERATURE
    assert first.evidence_type == EvidenceType.REVIEW  # publication types include "Systematic Review"
    assert first.identifiers.doi == "10.1002/alz.14338"
    assert first.identifiers.pmcid == "PMC11772739"
    assert first.publication_date == "2025-01"
    assert str(first.source_url) == "https://pubmed.ncbi.nlm.nih.gov/39776249/"
    assert first.summary and first.summary.startswith("INTRODUCTION:")
    assert first.metadata["content_scope"] == "abstract_only"
    assert len(first.authors) > 0


def test_missing_abstract_date_and_authors_are_tolerated() -> None:
    xml = """<PubmedArticleSet><PubmedArticle><MedlineCitation><PMID>1</PMID><Article>
      <Journal><JournalIssue><PubDate><MedlineDate>1998 Dec-1999 Jan</MedlineDate></PubDate></JournalIssue></Journal>
      <ArticleTitle>Bare <i>record</i></ArticleTitle>
      <PublicationTypeList><PublicationType>Editorial</PublicationType></PublicationTypeList>
    </Article></MedlineCitation><PubmedData><ArticleIdList/></PubmedData></PubmedArticle>
    <PubmedArticle><MedlineCitation><PMID>2</PMID><Article><ArticleTitle>No date</ArticleTitle></Article>
    </MedlineCitation></PubmedArticle></PubmedArticleSet>"""
    one, two = parse_pubmed_xml(xml)
    assert one.title == "Bare record"
    assert one.summary is None and one.authors == []
    assert one.publication_date == "1998-12"
    assert one.evidence_type == EvidenceType.UNKNOWN  # editorials are not upgraded to research
    assert two.publication_date is None


def test_invalid_xml_raises_source_error() -> None:
    with pytest.raises(SourceError):
        parse_pubmed_xml("<not-closed")


async def test_search_pubmed_end_to_end_with_mocked_http() -> None:
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.url.path)
        if request.url.path.endswith("esearch.fcgi"):
            assert request.url.params["term"] == "alzheimer tau"
            return httpx.Response(200, json=fixture_json("pubmed_esearch.json"))
        return httpx.Response(200, text=fixture_text("pubmed_efetch.xml"))

    async with mock_http(handler) as http:
        records = await search_pubmed(http, "alzheimer tau", max_results=2)
    assert len(records) == 2
    assert seen == ["/entrez/eutils/esearch.fcgi", "/entrez/eutils/efetch.fcgi"]


async def test_search_pubmed_no_hits_skips_efetch() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("esearch.fcgi")
        return httpx.Response(200, json={"esearchresult": {"idlist": []}})

    async with mock_http(handler) as http:
        assert await search_pubmed(http, "zzzz") == []
