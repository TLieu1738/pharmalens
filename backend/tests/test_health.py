from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


def test_root_returns_app_name_and_status(client: TestClient) -> None:
    response = client.get("/")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "running"
    assert body["name"] == "PharmaLens"


def test_health_reports_missing_integrations_as_degraded(client: TestClient) -> None:
    response = client.get("/api/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "degraded"
    assert body["checks"] == {"anthropic": "missing", "supabase": "missing"}
    assert body["storage"] == "in_memory"


def test_health_ok_when_configured_and_never_leaks_secrets() -> None:
    secret = "sk-ant-super-secret-value"
    configured = Settings(
        _env_file=None,
        environment="test",
        anthropic_api_key=secret,
        supabase_url="https://example.supabase.co",
        supabase_service_role_key="service-role-secret",
    )
    from app.services.repository import InMemorySessionRepository

    with TestClient(create_app(settings=configured, repo=InMemorySessionRepository())) as c:
        response = c.get("/api/health")
    assert response.json()["status"] == "ok"
    assert secret not in response.text
    assert "service-role-secret" not in response.text


def test_blank_model_env_falls_back_to_default() -> None:
    s = Settings(_env_file=None, anthropic_model="  ")
    assert s.anthropic_model.startswith("claude-")


def test_cors_origins_never_include_wildcard() -> None:
    s = Settings(
        _env_file=None, frontend_url="https://app.example.com/", additional_cors_origins="*, https://x.dev"
    )
    assert s.cors_origins == ["https://app.example.com", "https://x.dev"]
