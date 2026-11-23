"""Interactive research protocol: draft → review/edit → approve → run, plus cancel and re-run."""

from fastapi.testclient import TestClient

from tests.test_api_research import QUESTION, wait_for_status

ALICE = {"Authorization": "Bearer token-alice"}
BOB = {"Authorization": "Bearer token-bob"}


def _drafted(client: TestClient) -> tuple[str, dict]:
    sid = client.post("/api/research", json={"research_question": QUESTION}, headers=ALICE).json()[
        "session_id"
    ]
    body = wait_for_status(client, sid, ("awaiting_approval",), ALICE)
    return sid, body


def test_research_waits_for_approval_with_a_full_protocol(research_client: TestClient) -> None:
    sid, body = _drafted(research_client)
    plan = body["research_plan"]
    assert plan["objective"] and plan["key_questions"] and plan["inclusion_criteria"]
    assert plan["max_results_per_source"] == 50
    agents = {a["agent_name"]: a["status"] for a in body["agents"]}
    assert agents["research_planner"] == "completed"
    assert agents["literature_agent"] == "pending"  # nothing retrieved before approval
    assert research_client.get(f"/api/sessions/{sid}/evidence", headers=ALICE).json() == []


def test_edited_protocol_drives_the_run(research_client: TestClient) -> None:
    sid, body = _drafted(research_client)
    protocol = {
        **body["research_plan"],
        "sources": ["pubmed", "clinicaltrials_gov"],
        "max_results_per_source": 5,
        "inclusion_criteria": ["Randomised trials only"],
        "date_from": 2015,
        "date_to": 2025,
    }
    saved = research_client.put(f"/api/sessions/{sid}/protocol", json=protocol, headers=ALICE)
    assert saved.status_code == 200
    assert research_client.get(f"/api/sessions/{sid}", headers=ALICE).json()["research_plan"]["sources"] == [
        "pubmed",
        "clinicaltrials_gov",
    ]

    assert research_client.post(f"/api/sessions/{sid}/approve", json={}, headers=ALICE).status_code == 200
    done = wait_for_status(research_client, sid, ("completed", "failed"), ALICE)
    assert done["status"] == "completed"
    assert done["protocol_approved_at"]
    sources = {
        r["source_name"] for r in research_client.get(f"/api/sessions/{sid}/evidence", headers=ALICE).json()
    }
    assert sources <= {"pubmed", "clinicaltrials_gov"}
    agents = {a["agent_name"]: a for a in done["agents"]}
    assert agents["target_agent"]["status"] == "skipped"  # Open Targets was deselected
    lit = agents["literature_agent"]["sources"][0]
    assert lit["requested"] == 5 and lit["total_available"] is not None
    assert done["run_audit"]["limits"]["max_results_per_source"] == 5
    assert done["run_audit"]["limits"]["date_from"] == 2015


def test_protocol_validation(research_client: TestClient) -> None:
    sid, body = _drafted(research_client)
    plan = body["research_plan"]
    for bad in (
        {**plan, "sources": []},
        {**plan, "max_results_per_source": 500},
        {**plan, "date_from": 2024, "date_to": 2010},
        {**plan, "literature_query": "   "},
    ):
        assert (
            research_client.put(f"/api/sessions/{sid}/protocol", json=bad, headers=ALICE).status_code == 422
        )


def test_protocol_locks_after_approval_and_is_private(research_client: TestClient) -> None:
    sid, body = _drafted(research_client)
    plan = body["research_plan"]
    assert research_client.put(f"/api/sessions/{sid}/protocol", json=plan, headers=BOB).status_code == 404
    assert research_client.post(f"/api/sessions/{sid}/approve", json={}, headers=BOB).status_code == 404
    assert research_client.post(f"/api/sessions/{sid}/cancel", headers=BOB).status_code == 404

    assert (
        research_client.post(
            f"/api/sessions/{sid}/approve", json={"protocol": plan}, headers=ALICE
        ).status_code
        == 200
    )
    assert research_client.put(f"/api/sessions/{sid}/protocol", json=plan, headers=ALICE).status_code == 409
    assert research_client.post(f"/api/sessions/{sid}/approve", json={}, headers=ALICE).status_code == 409


def test_cancel_before_approval(research_client: TestClient) -> None:
    sid, _ = _drafted(research_client)
    assert research_client.post(f"/api/sessions/{sid}/cancel", headers=ALICE).json()["status"] == "cancelled"
    assert research_client.post(f"/api/sessions/{sid}/approve", json={}, headers=ALICE).status_code == 409
    assert research_client.post(f"/api/sessions/{sid}/cancel", headers=ALICE).status_code == 409


def test_rerun_reopens_the_protocol_for_editing(research_client: TestClient) -> None:
    sid, body = _drafted(research_client)
    r = research_client.post(f"/api/sessions/{sid}/rerun", headers=ALICE)
    assert r.status_code == 201
    new = research_client.get(f"/api/sessions/{r.json()['session_id']}", headers=ALICE).json()
    assert new["status"] == "awaiting_approval"
    assert new["research_plan"]["literature_query"] == body["research_plan"]["literature_query"]
    assert new["research_question"] == body["research_question"]
