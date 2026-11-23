"""API-level tests: request validation, background execution, polling, evidence, ownership, limits."""

import time

from fastapi.testclient import TestClient

QUESTION = "Investigate Alzheimer's disease research focusing on amyloid-beta and tau."


def wait_for_status(
    client: TestClient, sid: str, statuses: tuple[str, ...], headers: dict[str, str] | None = None
) -> dict:
    deadline = time.time() + 10
    while time.time() < deadline:
        body = client.get(f"/api/sessions/{sid}", headers=headers or {}).json()
        if body["status"] in statuses:
            return body
        time.sleep(0.02)
    raise AssertionError(f"session never reached {statuses}")


def wait_for_terminal(client: TestClient, sid: str, headers: dict[str, str] | None = None) -> dict:
    """Wait for the drafted protocol, approve it unchanged (as a user would), then wait for the result."""
    body = wait_for_status(client, sid, ("awaiting_approval", "failed"), headers)
    if body["status"] == "awaiting_approval":
        assert client.post(f"/api/sessions/{sid}/approve", json={}, headers=headers or {}).status_code == 200
        body = wait_for_status(client, sid, ("completed", "failed", "cancelled"), headers)
    return body


def test_validation_rejects_bad_questions(research_client: TestClient) -> None:
    for q in ["", "short", "a b c d e f g h i j k l m n o", "!!!! ???? !!!! ???? !!!!", "x" * 2001]:
        r = research_client.post("/api/research", json={"research_question": q})
        assert r.status_code == 422, q
    assert research_client.post("/api/research", json={}).status_code == 422


def test_without_anthropic_key_returns_503(client: TestClient) -> None:
    r = client.post("/api/research", json={"research_question": QUESTION})
    assert r.status_code == 503
    assert "not configured" in r.json()["detail"]


def test_anonymous_research_end_to_end(research_client: TestClient) -> None:
    r = research_client.post("/api/research", json={"research_question": QUESTION})
    assert r.status_code == 202
    sid = r.json()["session_id"]
    assert r.json()["status"] == "pending"

    body = wait_for_terminal(research_client, sid)
    assert body["status"] == "completed", body.get("error_message")
    assert body["demo_mode"] is True and body["is_owner"] is False
    assert [a["agent_name"] for a in body["agents"]][0] == "research_planner"
    assert all(a["status"] == "completed" for a in body["agents"])
    assert body["research_plan"]["disease_area"] == "Alzheimer disease"
    assert body["report"]["references"]
    assert body["report"]["disclaimer"]

    evidence = research_client.get(f"/api/sessions/{sid}/evidence").json()
    assert len(evidence) == body["evidence_profile"]["total_records"]
    ids = {e["record_id"] for e in evidence}
    assert all(ref["record_id"] in ids for ref in body["report"]["references"])


def test_owned_sessions_are_private(research_client: TestClient) -> None:
    alice = {"Authorization": "Bearer token-alice"}
    bob = {"Authorization": "Bearer token-bob"}
    sid = research_client.post("/api/research", json={"research_question": QUESTION}, headers=alice).json()[
        "session_id"
    ]
    body = wait_for_terminal(research_client, sid, alice)
    assert body["is_owner"] is True and body["demo_mode"] is False

    assert research_client.get(f"/api/sessions/{sid}").status_code == 404
    assert research_client.get(f"/api/sessions/{sid}", headers=bob).status_code == 404
    assert research_client.get(f"/api/sessions/{sid}/evidence", headers=bob).status_code == 404

    listed = research_client.get("/api/sessions", headers=alice).json()
    assert [s["session_id"] for s in listed] == [sid]
    assert research_client.get("/api/sessions", headers=bob).json() == []


def test_auth_errors(research_client: TestClient) -> None:
    assert research_client.get("/api/sessions").status_code == 401
    assert research_client.get("/api/sessions", headers={"Authorization": "Bearer nope"}).status_code == 401
    assert research_client.get("/api/sessions", headers={"Authorization": "Basic x"}).status_code == 401


def test_unknown_and_malformed_session_ids(research_client: TestClient) -> None:
    assert research_client.get("/api/sessions/not-a-uuid").status_code == 404
    assert research_client.get("/api/sessions/00000000-0000-0000-0000-000000000000").status_code == 404


def test_anonymous_rate_limit(research_client: TestClient) -> None:
    for _ in range(2):
        assert research_client.post("/api/research", json={"research_question": QUESTION}).status_code == 202
    r = research_client.post("/api/research", json={"research_question": QUESTION})
    assert r.status_code == 429
    # Signed-in users are not subject to the anonymous quota.
    ok = research_client.post(
        "/api/research", json={"research_question": QUESTION}, headers={"Authorization": "Bearer token-carol"}
    )
    assert ok.status_code == 202


def test_library_merges_users_evidence_and_is_private(research_client: TestClient) -> None:
    alice = {"Authorization": "Bearer token-alice"}
    bob = {"Authorization": "Bearer token-bob"}
    sids = []
    for _ in range(2):
        sid = research_client.post(
            "/api/research", json={"research_question": QUESTION}, headers=alice
        ).json()["session_id"]
        wait_for_terminal(research_client, sid, alice)
        sids.append(sid)

    library = research_client.get("/api/library", headers=alice).json()
    per_session = research_client.get(f"/api/sessions/{sids[0]}/evidence", headers=alice).json()
    # Same mocked sources twice: records are deduplicated, each linked to both sessions.
    assert len(library) == len(per_session) > 0
    assert len({r["record_id"] for r in library}) == len(library)
    assert all({s["session_id"] for s in r["sessions"]} == set(sids) for r in library)

    assert research_client.get("/api/library", headers=bob).json() == []
    assert research_client.get("/api/library").status_code == 401
