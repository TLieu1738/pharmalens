"""PubChem, OpenAlex and ChEMBL target integrations (Phase 2), all on fixtures recorded from the live APIs."""

import copy

import httpx
import pytest

from app.integrations.chembl import parse_target, search_compounds
from app.integrations.http import SourceError
from app.integrations.openalex import abstract_from_index, build_filter, parse_openalex, search_openalex_paged
from app.integrations.provenance import make_provenance
from app.integrations.pubchem import lookup_by_inchikey
from app.models.evidence import EvidenceCategory, EvidenceRecord, EvidenceType, Identifiers, SourceName
from app.services.evidence_processing import deduplicate
from app.services.record_checks import record_problems
from tests.helpers import fixture_json, mock_http

DONEPEZIL_KEY = "ADEBPBSSDYVVLD-UHFFFAOYSA-N"


def chembl_record(chembl_id: str = "CHEMBL502", inchi_key: str | None = DONEPEZIL_KEY) -> EvidenceRecord:
    return EvidenceRecord(
        record_id=f"chembl:{chembl_id}",
        source_name=SourceName.CHEMBL,
        source_identifier=chembl_id,
        category=EvidenceCategory.COMPOUND,
        evidence_type=EvidenceType.DATABASE_RECORD,
        title="Donepezil",
        source_url=f"https://www.ebi.ac.uk/chembl/explore/compound/{chembl_id}",
        provenance=make_provenance(
            "chembl", f"https://www.ebi.ac.uk/chembl/api/data/molecule/{chembl_id}.json", {}
        ),
        identifiers=Identifiers(chembl_id=chembl_id),
        metadata={"inchi_key": inchi_key},
    )


# ------------------------------------------------------------------------------------------------- OpenAlex
def test_openalex_parses_real_works() -> None:
    records = parse_openalex(fixture_json("openalex_works.json"))
    assert len(records) == 3
    first = records[0]
    assert first.record_id == "openalex:W4390199458"
    assert first.identifiers.doi == "10.1002/alz.080907"  # https://doi.org/ prefix removed
    assert first.identifiers.openalex_id == "W4390199458"
    assert first.title.startswith("Lecanemab")
    assert first.summary  # rebuilt from the inverted index
    assert "Eisai (United States)" in first.metadata["institutions"]
    assert isinstance(first.metadata["cited_by_count"], int)
    assert first.provenance and first.provenance.api_url == "https://api.openalex.org/works/W4390199458"
    assert all(record_problems(r) == [] for r in records)


def test_abstract_is_rebuilt_in_word_order() -> None:
    assert (
        abstract_from_index({"world": [1], "hello": [0], "again": [3], "hello,": [2]})
        == "hello world hello, again"
    )
    assert abstract_from_index(None) is None and abstract_from_index({}) is None


def test_openalex_preprint_and_retraction_are_flagged_from_source_fields() -> None:
    data = copy.deepcopy(fixture_json("openalex_works.json"))
    data["results"][0]["type"] = "preprint"
    data["results"][1]["is_retracted"] = True
    preprint, retracted, _ = parse_openalex(data)
    assert preprint.evidence_type == EvidenceType.PREPRINT
    assert "Retracted Publication" in retracted.publication_types


def test_openalex_filters() -> None:
    assert build_filter(date_from=None, date_to=None, include_preprints=True) is None
    assert (
        build_filter(date_from=2018, date_to=2024, include_preprints=False)
        == "from_publication_date:2018-01-01,to_publication_date:2024-12-31,type:!preprint"
    )


async def test_openalex_paging_sends_key_but_never_stores_it() -> None:
    seen: list[httpx.URL] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.url)
        return httpx.Response(200, json=fixture_json("openalex_works.json"))

    async with mock_http(handler) as http:
        page = await search_openalex_paged(
            http, "lecanemab", max_results=3, date_from=2020, include_preprints=False, api_key="secret-key"
        )
    assert len(page.records) == 3 and page.total_available == 8649 and page.pages == 1
    params = seen[0].params
    assert params["api_key"] == "secret-key" and params["per-page"] == "3"
    assert params["filter"] == "from_publication_date:2020-01-01,type:!preprint"
    assert all("secret-key" not in (r.provenance.api_url if r.provenance else "") for r in page.records)
    assert "secret-key" not in page.query


async def test_openalex_refusal_is_a_source_failure_not_an_empty_result() -> None:
    async with mock_http(lambda r: httpx.Response(429), max_retries=0) as http:
        with pytest.raises(SourceError):
            await search_openalex_paged(http, "lecanemab", max_results=5)


def test_openalex_record_merges_with_pubmed_copy_by_doi() -> None:
    (oa, *_) = parse_openalex(fixture_json("openalex_works.json"))
    pubmed = EvidenceRecord(
        record_id="pubmed:38000001",
        source_name=SourceName.PUBMED,
        source_identifier="38000001",
        category=EvidenceCategory.LITERATURE,
        evidence_type=EvidenceType.PRIMARY_RESEARCH,
        title=oa.title,
        source_url="https://pubmed.ncbi.nlm.nih.gov/38000001/",
        identifiers=Identifiers(pmid="38000001", doi=oa.identifiers.doi.upper()),
    )
    (merged,), removed = deduplicate([oa, pubmed])
    assert removed == 1
    assert merged.record_id == "pubmed:38000001"  # PubMed stays canonical
    assert SourceName.OPENALEX in merged.also_found_in
    assert merged.identifiers.openalex_id == "W4390199458"
    assert merged.metadata["institutions"] == oa.metadata["institutions"]


# -------------------------------------------------------------------------------------------------- PubChem
async def test_pubchem_links_by_inchikey() -> None:
    urls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        urls.append(str(request.url))
        return httpx.Response(200, json=fixture_json("pubchem_properties.json"))

    async with mock_http(handler) as http:
        (rec,) = await lookup_by_inchikey(http, [chembl_record(), chembl_record("CHEMBL1", inchi_key=None)])
    assert len(urls) == 1 and f"/inchikey/{DONEPEZIL_KEY}/" in urls[0]  # biologic without a key: no request
    assert rec.record_id == "pubchem:3152" and rec.title == "Donepezil"
    assert rec.metadata["linked_chembl_id"] == "CHEMBL502"
    assert rec.metadata["molecular_formula"] == "C24H29NO3"
    assert rec.identifiers.chembl_id is None  # stays a separate record; linked, not merged
    assert record_problems(rec) == []


async def test_pubchem_not_found_is_skipped_but_outage_fails() -> None:
    async with mock_http(lambda r: httpx.Response(404, json={"Fault": {}}), max_retries=0) as http:
        assert await lookup_by_inchikey(http, [chembl_record()]) == []
    async with mock_http(lambda r: httpx.Response(503), max_retries=0) as http:
        with pytest.raises(SourceError):
            await lookup_by_inchikey(http, [chembl_record()])


async def test_pubchem_ignores_a_different_structure() -> None:
    data = copy.deepcopy(fixture_json("pubchem_properties.json"))
    data["PropertyTable"]["Properties"][0]["InChIKey"] = "BSYNRYMUTXBXSQ-UHFFFAOYSA-N"
    async with mock_http(lambda r: httpx.Response(200, json=data)) as http:
        assert await lookup_by_inchikey(http, [chembl_record()]) == []


# -------------------------------------------------------------------------------------------- ChEMBL targets
def test_chembl_target_gene_symbols_only_official() -> None:
    info = parse_target(fixture_json("chembl_target.json"))
    assert info["target_gene_symbols"] == ["APP"]  # GENE_SYMBOL_OTHER ("AD1") excluded
    assert info["target_name"] == "Amyloid-beta precursor protein"
    assert parse_target(fixture_json("chembl_mechanism.json")) == {}


async def test_chembl_mechanisms_carry_target_symbols() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path.endswith("/molecule/search.json"):
            return httpx.Response(200, json=fixture_json("chembl_molecule_search.json"))
        if "/target/" in path:
            return httpx.Response(200, json=fixture_json("chembl_target.json"))
        return httpx.Response(200, json=fixture_json("chembl_mechanism.json"))

    async with mock_http(handler) as http:
        (rec,) = await search_compounds(http, ["lecanemab"])
    mech = rec.metadata["mechanisms"][0]
    assert mech["target_chembl_id"] == "CHEMBL2487" and mech["target_gene_symbols"] == ["APP"]
    assert rec.metadata["inchi_key"] is None  # antibody: no small-molecule structure


async def test_chembl_mechanisms_are_looked_up_by_parent_molecule() -> None:
    """Mechanisms filed under a salt form (e.g. donepezil hydrochloride) must still be found for the parent drug."""
    mech_params: list[dict[str, str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/molecule/search.json"):
            return httpx.Response(200, json=fixture_json("chembl_molecule_search.json"))
        if request.url.path.endswith("/mechanism.json"):
            mech_params.append(dict(request.url.params))
        return httpx.Response(200, json=fixture_json("chembl_mechanism.json"))

    async with mock_http(handler) as http:
        await search_compounds(http, ["lecanemab"])
    assert mech_params and all(p.get("parent_molecule_chembl_id") == "CHEMBL3833321" for p in mech_params)
    assert all("molecule_chembl_id" not in p for p in mech_params)


# ------------------------------------------------------------------------------------------- record checks
def test_new_sources_reject_malformed_records() -> None:
    (oa, *_) = parse_openalex(fixture_json("openalex_works.json"))
    bad_id = oa.model_copy(update={"source_identifier": "12345", "record_id": "openalex:12345"})
    assert any("not a valid openalex identifier" in p for p in record_problems(bad_id))
    wrong_host = oa.model_copy(update={"source_url": "https://example.com/W4390199458"})
    assert any("source URL" in p for p in record_problems(wrong_host))
