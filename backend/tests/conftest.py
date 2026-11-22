from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.services.auth import AuthError, AuthUser
from app.services.repository import InMemorySessionRepository
from tests.fakes import FakeLLM, source_router
from tests.helpers import mock_http


@pytest.fixture
def settings() -> Settings:
    # _env_file=None isolates tests from a developer's local .env
    return Settings(_env_file=None, environment="test", anthropic_api_key=None, supabase_url=None)


class FakeAuth:
    """Maps bearer tokens to users: 'token-alice' -> alice, anything else is rejected."""

    enabled = True

    async def verify(self, token: str) -> AuthUser:
        if token.startswith("token-"):
            name = token.removeprefix("token-")
            return AuthUser(
                id=f"00000000-0000-0000-0000-{name.encode().hex()[:12].ljust(12, '0')}", email=None
            )
        raise AuthError("invalid or expired session")

    async def aclose(self) -> None:
        return None


@pytest.fixture
def client(settings: Settings) -> Iterator[TestClient]:
    app = create_app(settings=settings, repo=InMemorySessionRepository())
    with TestClient(app) as c:
        yield c


@pytest.fixture
def research_client() -> Iterator[TestClient]:
    """App wired with a fake LLM, mocked sources, in-memory storage and fake auth."""
    settings = Settings(
        _env_file=None, environment="test", anon_sessions_per_hour=2, max_concurrent_research=5
    )
    app = create_app(
        settings=settings, repo=InMemorySessionRepository(), llm=FakeLLM(), http=mock_http(source_router())
    )
    with TestClient(app) as c:
        app.state.services.auth = FakeAuth()
        yield c
