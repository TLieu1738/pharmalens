import httpx
import pytest

from app.integrations.chembl import search_compounds
from app.integrations.http import SourceError
from app.integrations.open_targets import disease_targets, parse_associations
from app.models.evidence import EvidenceCategory
from tests.helpers import fixture_json, mock_http


async def test_chembl_search_with_mechanism() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/molecule/search.json"):
            return httpx.Response(200, json=fixture_json("chembl_molecule_search.json"))
        return httpx.Response(200, json=fixture_json("chembl_mechanism.json"))

    async with mock_http(handler) as http:
        (rec,) = await search_compounds(http, ["lecanemab"])
    assert rec.record_id == "chembl:CHEMBL3833321"
    assert rec.category == EvidenceCategory.COMPOUND
    assert rec.title == "Lecanemab"
    assert rec.metadata["max_phase"] == 4.0
    assert "at least one indication" in rec.metadata["max_phase_label"]
    assert rec.metadata["mechanisms"][0]["target_chembl_id"] == "CHEMBL2487"
    assert str(rec.source_url).endswith("/compound/CHEMBL3833321")


async def test_chembl_partial_failure_is_not_fatal_but_total_failure_is() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.params.get("q") == "broken":
            return httpx.Response(500)
        if request.url.path.endswith("/molecule/search.json"):
            return httpx.Response(200, json=fixture_json("chembl_molecule_search.json"))
        return httpx.Response(500)  # mechanism lookups fail -> still returns molecule

    async with mock_http(handler, max_retries=0) as http:
        records = await search_compounds(http, ["lecanemab", "broken"])
        assert len(records) == 1 and records[0].metadata["mechanisms"] == []
        with pytest.raises(SourceError):
            await search_compounds(http, ["broken"])


async def test_open_targets_disease_associations() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        body = request.read().decode()
        name = "open_targets_search.json" if "DiseaseSearch" in body else "open_targets_associations.json"
        return httpx.Response(200, json=fixture_json(name))

    async with mock_http(handler) as http:
        records = await disease_targets(http, "Alzheimer disease", focus_targets=["APP"])
    assert records[0].identifiers.ensembl_id == "ENSG00000142192"
    assert records[0].metadata["target_symbol"] == "APP"
    assert records[0].metadata["matches_question_focus"] is True
    assert records[0].metadata["association_rank"] == 1
    assert "does not establish causation" in (records[0].summary or "")


def test_open_targets_graphql_errors_raise() -> None:
    with pytest.raises(SourceError):
        parse_associations({"errors": [{"message": "bad"}]}, focus_targets=[])
