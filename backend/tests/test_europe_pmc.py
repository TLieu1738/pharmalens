import httpx
import pytest

from app.integrations.europe_pmc import parse_europe_pmc, search_europe_pmc
from app.integrations.http import SourceError
from app.models.evidence import EvidenceType
from tests.helpers import fixture_json, mock_http


def test_parse_real_fixture_including_preprint() -> None:
    records = parse_europe_pmc(fixture_json("europe_pmc_search.json"))
    assert len(records) == 3
    med = records[0]
    assert med.record_id == "europe_pmc:MED:43056657"
    assert med.identifiers.pmid == "43056657"
    assert med.publication_date == "2026-11-19"
    assert str(med.source_url) == "https://europepmc.org/article/MED/43056657"
    preprint = records[2]
    assert preprint.evidence_type == EvidenceType.PREPRINT
    assert preprint.metadata["europe_pmc_source"] == "PPR"


def test_missing_fields_are_tolerated_and_bad_items_skipped() -> None:
    data = {
        "resultList": {
            "result": [
                {"id": "1", "source": "MED", "title": "Minimal"},
                {"source": "MED"},  # no id/title -> skipped
            ]
        }
    }
    (rec,) = parse_europe_pmc(data)
    assert rec.summary is None and rec.publication_date is None and rec.authors == []
    assert rec.evidence_type == EvidenceType.UNKNOWN


def test_unexpected_shape_raises() -> None:
    with pytest.raises(SourceError):
        parse_europe_pmc({"oops": True})


async def test_retries_transient_503_then_succeeds() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            return httpx.Response(503)
        return httpx.Response(200, json=fixture_json("europe_pmc_search.json"))

    async with mock_http(handler) as http:
        records = await search_europe_pmc(http, "tau")
    assert calls == 2 and len(records) == 3


async def test_gives_up_after_bounded_retries() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(503)

    async with mock_http(handler, max_retries=2) as http:
        with pytest.raises(SourceError):
            await search_europe_pmc(http, "tau")
    assert calls == 3
