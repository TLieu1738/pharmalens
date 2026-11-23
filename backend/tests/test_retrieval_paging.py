"""Paged retrieval, protocol filters, multi-query literature search, coverage reporting and grounding audit."""

import httpx

from app.agents.literature import retrieve_literature
from app.agents.verification import verify_report
from app.integrations.clinical_trials import search_clinical_trials_paged
from app.integrations.europe_pmc import build_query, search_europe_pmc_paged
from app.integrations.open_targets import parse_associations
from app.integrations.pubmed import parse_pubmed_xml, search_pubmed_paged
from app.models.evidence import EvidenceRecord
from app.models.research import ResearchPlan
from app.services.evidence_processing import process_evidence
from app.services.research_service import build_audit
from tests.fakes import PLAN, synthesis_output
from tests.helpers import fixture_json, fixture_text, mock_http


async def test_pubmed_pages_with_retstart_and_applies_dates() -> None:
    seen: list[dict[str, str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("esearch.fcgi"):
            params = dict(request.url.params)
            seen.append(params)
            start = int(params["retstart"])
            ids = [str(1000 + start + i) for i in range(int(params["retmax"]))]
            return httpx.Response(200, json={"esearchresult": {"count": "120", "idlist": ids}})
        return httpx.Response(200, text="<PubmedArticleSet></PubmedArticleSet>")

    async with mock_http(handler) as http:
        page = await search_pubmed_paged(http, "tau", max_results=70, date_from=2015, date_to=2020)
    assert [p["retstart"] for p in seen] == ["0", "50"]
    assert [p["retmax"] for p in seen] == ["50", "20"]
    assert seen[0]["mindate"] == "2015" and seen[0]["maxdate"] == "2020" and seen[0]["datetype"] == "pdat"
    assert page.total_available == 120 and page.pages == 2


async def test_pubmed_stops_when_the_source_runs_out() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        if request.url.path.endswith("esearch.fcgi"):
            calls += 1
            return httpx.Response(200, json=fixture_json("pubmed_esearch.json"))
        return httpx.Response(200, text=fixture_text("pubmed_efetch.xml"))

    async with mock_http(handler) as http:
        await search_pubmed_paged(http, "tau", max_results=60)
    assert calls == 1  # fewer ids than asked = no further pages


def test_europe_pmc_query_filters() -> None:
    assert build_query("tau", date_from=None, date_to=None, include_preprints=True) == "tau"
    q = build_query("tau", date_from=2018, date_to=None, include_preprints=False)
    assert q == "(tau) AND (PUB_YEAR:[2018 TO 3000]) NOT (SRC:PPR)"


async def test_europe_pmc_follows_cursor_and_reports_hit_count() -> None:
    cursors: list[str] = []
    data = fixture_json("europe_pmc_search.json")
    per_page = len(data["resultList"]["result"])  # type: ignore[index]

    def handler(request: httpx.Request) -> httpx.Response:
        cursors.append(request.url.params["cursorMark"])
        return httpx.Response(
            200,
            json={**data, "hitCount": 999, "nextCursorMark": f"c{len(cursors)}"},  # type: ignore[dict-item]
        )

    async with mock_http(handler) as http:
        # a full page of `per_page` records, then the next page via the cursor
        page = await search_europe_pmc_paged(http, "tau", max_results=per_page * 2, page_size=per_page)
    assert cursors == ["*", "c1"]
    assert page.total_available == 999 and len(page.records) == per_page * 2 and page.truncated


async def test_clinical_trials_page_token_and_start_date_filter() -> None:
    seen: list[dict[str, str]] = []
    data = fixture_json("clinical_trials_studies.json")
    n = len(data["studies"])  # type: ignore[index]

    def handler(request: httpx.Request) -> httpx.Response:
        params = dict(request.url.params)
        seen.append(params)
        return httpx.Response(
            200, json={**data, "totalCount": 40, "nextPageToken": "t2" if len(seen) == 1 else None}
        )  # type: ignore[dict-item]

    async with mock_http(handler) as http:
        page = await search_clinical_trials_paged(
            http,
            condition="Alzheimer Disease",
            max_results=n * 2,
            start_from=2018,
            start_to=None,
            page_size=n,
        )
    assert seen[0]["filter.advanced"] == "AREA[StartDate]RANGE[2018-01-01,MAX]"
    assert "pageToken" not in seen[0] and seen[1]["pageToken"] == "t2"
    assert page.total_available == 40 and len(page.records) == n * 2


async def test_literature_runs_every_query_and_records_coverage() -> None:
    queries: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if "europepmc" in request.url.path:
            queries.append(request.url.params["query"])
            return httpx.Response(200, json={**fixture_json("europe_pmc_search.json"), "hitCount": 500})  # type: ignore[dict-item]
        return httpx.Response(404)

    plan = ResearchPlan(
        **{
            **PLAN.model_dump(),
            "sources": ["europe_pmc"],
            "max_results_per_source": 10,
            "additional_literature_queries": ["tau PET imaging"],
        }
    )
    async with mock_http(handler) as http:
        result = await retrieve_literature(http, plan)
    assert set(queries) == {plan.literature_query, "tau PET imaging"}
    assert all(s.requested == 5 and s.total_available == 500 and s.query for s in result.sources)
    assert len({r.record_id for r in result.records}) == len(
        result.records
    )  # within-source duplicates dropped
    assert any("top" in w and "500" in w for w in result.warnings)  # truncation is stated, not hidden


def _records() -> list[EvidenceRecord]:
    """Records parsed from the recorded fixtures (the fake synthesis output cites some of them)."""
    pubmed = parse_pubmed_xml(fixture_text("pubmed_efetch.xml"))
    targets = parse_associations(fixture_json("open_targets_associations.json"), focus_targets=[])
    return [*pubmed, *targets]


async def test_grounding_records_what_was_removed_and_why() -> None:
    report = await verify_report(
        None,
        synthesis_output(),
        _records(),
        persisted_ids=None,
        context_numbers=[],
        question="q",
        scope="s",
        model="m",
        records_provided=len(_records()),
    )
    removed = report.integrity.removed_statements
    assert [r.reason for r in removed] == ["finding with no citation"]
    assert removed[0].section == "Executive summary"
    assert report.integrity.invalid_citations == ["pubmed:00000000"]
    assert [s.key for s in report.sections][-1] == "conclusions"
    assert report.integrity.records_available == len(_records())


def test_audit_lists_merged_duplicates() -> None:
    pubmed = [r for r in _records() if r.source_name.value == "pubmed"][0]
    twin = pubmed.model_copy(
        update={"record_id": "europe_pmc:MED:" + pubmed.source_identifier, "source_name": "europe_pmc"}
    )
    validated, removed = process_evidence([pubmed, twin])
    assert removed == 1
    state = {"literature_records": [pubmed, twin], "validated_evidence": validated, "errors": []}
    from datetime import UTC, datetime

    audit = build_audit(
        state, model="m", attempts=1, started=datetime.now(UTC), plan=ResearchPlan(**PLAN.model_dump())
    )  # type: ignore[arg-type]
    assert audit["deduplication"]["duplicates_merged"] == 1
    assert audit["deduplication"]["merges"][0]["merged"] == [twin.record_id]
    assert "secret" not in str(audit).lower()
