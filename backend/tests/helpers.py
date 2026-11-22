"""Shared test helpers: fixture loading and a mock HTTP transport for SourceHttpClient."""

import json
from collections.abc import Callable
from pathlib import Path

import httpx

from app.integrations.http import SourceHttpClient

FIXTURES = Path(__file__).parent / "fixtures"


def fixture_text(name: str) -> str:
    return (FIXTURES / name).read_text()


def fixture_json(name: str) -> object:
    return json.loads(fixture_text(name))


Handler = Callable[[httpx.Request], httpx.Response]


def mock_http(handler: Handler, **kwargs: object) -> SourceHttpClient:
    """SourceHttpClient whose requests are served by `handler` (no network). Backoff is zeroed."""
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return SourceHttpClient(client, backoff_base=0, **kwargs)  # type: ignore[arg-type]
