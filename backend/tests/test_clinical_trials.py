import httpx

from app.integrations.clinical_trials import parse_studies, search_clinical_trials
from app.models.evidence import EvidenceType
from tests.helpers import fixture_json, mock_http


def test_parse_real_fixture() -> None:
    records = parse_studies(fixture_json("clinical_trials_studies.json"))
    assert [r.source_identifier for r in records] == ["NCT05215782", "NCT06325527"]
    trial = records[0]
    assert trial.evidence_type == EvidenceType.CLINICAL_TRIAL
    assert str(trial.source_url) == "https://clinicaltrials.gov/study/NCT05215782"
    assert trial.identifiers.nct_id == "NCT05215782"
    assert trial.metadata["overall_status"] == "COMPLETED"
    assert trial.metadata["study_type"] == "Observational"
    assert trial.metadata["start_date"] == "2022-03-14"
    assert trial.metadata["has_results"] is False


def test_phases_and_interventions_normalised() -> None:
    data = {
        "studies": [
            {
                "protocolSection": {
                    "identificationModule": {"nctId": "NCT00000001", "briefTitle": "T"},
                    "statusModule": {"overallStatus": "TERMINATED", "whyStopped": "Futility"},
                    "designModule": {"phases": ["PHASE2", "PHASE3"], "studyType": "INTERVENTIONAL"},
                    "armsInterventionsModule": {"interventions": [{"name": "Drug X", "type": "DRUG"}]},
                },
                "hasResults": True,
            }
        ]
    }
    (rec,) = parse_studies(data)
    assert rec.metadata["phases"] == ["Phase 2", "Phase 3"]
    assert rec.metadata["interventions"] == [{"name": "Drug X", "type": "Drug"}]
    assert rec.metadata["why_stopped"] == "Futility"
    assert rec.publication_date is None


async def test_query_params_and_empty_query() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["query.cond"] == "Alzheimer Disease"
        assert request.url.params["query.intr"] == "lecanemab"
        return httpx.Response(200, json=fixture_json("clinical_trials_studies.json"))

    async with mock_http(handler) as http:
        assert (
            len(await search_clinical_trials(http, condition="Alzheimer Disease", intervention="lecanemab"))
            == 2
        )
        assert await search_clinical_trials(http, condition=None) == []
