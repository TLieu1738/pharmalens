"""Shared HTTP plumbing for external scientific APIs.

All source integrations go through :class:`SourceHttpClient`, which adds:
- sensible timeouts and a descriptive User-Agent;
- bounded exponential backoff on transient failures (network errors, 429, 5xx);
- per-host concurrency limits so we stay polite to public APIs;
- a small in-memory TTL cache to avoid repeating identical requests.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import time
from typing import Any
from urllib.parse import urlsplit

import httpx

logger = logging.getLogger(__name__)

USER_AGENT = "PharmaLens/0.1 (biomedical research-support prototype)"
RETRYABLE_STATUS = {429, 500, 502, 503, 504}


class SourceError(Exception):
    """Raised when an external source cannot be queried successfully (after retries)."""

    def __init__(self, source: str, message: str) -> None:
        super().__init__(f"{source}: {message}")
        self.source = source
        self.message = message


class _TTLCache:
    def __init__(self, ttl_seconds: float, max_entries: int = 512) -> None:
        self._ttl = ttl_seconds
        self._max = max_entries
        self._data: dict[str, tuple[float, Any]] = {}

    def get(self, key: str) -> Any | None:
        hit = self._data.get(key)
        if hit is None:
            return None
        expires, value = hit
        if expires < time.monotonic():
            self._data.pop(key, None)
            return None
        return value

    def set(self, key: str, value: Any) -> None:
        if len(self._data) >= self._max:
            self._data.pop(next(iter(self._data)))
        self._data[key] = (time.monotonic() + self._ttl, value)


class SourceHttpClient:
    def __init__(
        self,
        client: httpx.AsyncClient | None = None,
        *,
        timeout: float = 20.0,
        max_retries: int = 2,
        backoff_base: float = 0.75,
        cache_ttl_seconds: float = 900.0,
        per_host_concurrency: int = 3,
    ) -> None:
        self._client = client or httpx.AsyncClient(
            timeout=httpx.Timeout(timeout), headers={"User-Agent": USER_AGENT}, follow_redirects=True
        )
        self._owns_client = client is None
        self._max_retries = max_retries
        self._backoff_base = backoff_base
        self._cache = _TTLCache(cache_ttl_seconds)
        self._per_host_concurrency = per_host_concurrency
        self._semaphores: dict[str, asyncio.Semaphore] = {}

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def __aenter__(self) -> SourceHttpClient:
        return self

    async def __aexit__(self, *_: object) -> None:
        await self.aclose()

    def _semaphore(self, url: str) -> asyncio.Semaphore:
        host = urlsplit(url).netloc
        if host not in self._semaphores:
            self._semaphores[host] = asyncio.Semaphore(self._per_host_concurrency)
        return self._semaphores[host]

    async def request(
        self,
        source: str,
        method: str,
        url: str,
        *,
        params: dict[str, Any] | None = None,
        json_body: Any = None,
        expect: str = "json",
    ) -> Any:
        """Perform a request and return parsed JSON (``expect='json'``) or text (``expect='text'``)."""
        cache_key = hashlib.sha256(
            json.dumps([method, url, params, json_body, expect], sort_keys=True, default=str).encode()
        ).hexdigest()
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached

        last_error = "unknown error"
        for attempt in range(self._max_retries + 1):
            started = time.perf_counter()
            try:
                async with self._semaphore(url):
                    response = await self._client.request(method, url, params=params, json=json_body)
                elapsed_ms = int((time.perf_counter() - started) * 1000)
                logger.info(
                    "source_request source=%s status=%s attempt=%d elapsed_ms=%d",
                    source,
                    response.status_code,
                    attempt + 1,
                    elapsed_ms,
                )
                if response.status_code in RETRYABLE_STATUS:
                    last_error = f"HTTP {response.status_code}"
                    retry_after = _retry_after_seconds(response)
                    if attempt < self._max_retries:
                        await asyncio.sleep(retry_after or self._backoff_base * (2**attempt))
                        continue
                    break
                if response.status_code >= 400:
                    raise SourceError(source, f"HTTP {response.status_code}")
                value = response.json() if expect == "json" else response.text
                self._cache.set(cache_key, value)
                return value
            except (httpx.TimeoutException, httpx.TransportError) as exc:
                last_error = type(exc).__name__
                logger.warning(
                    "source_request_error source=%s attempt=%d error=%s", source, attempt + 1, last_error
                )
                if attempt < self._max_retries:
                    await asyncio.sleep(self._backoff_base * (2**attempt))
                    continue
            except ValueError as exc:  # invalid JSON
                raise SourceError(source, "invalid response body") from exc
        raise SourceError(source, f"request failed after {self._max_retries + 1} attempts ({last_error})")

    async def get_json(self, source: str, url: str, params: dict[str, Any] | None = None) -> Any:
        return await self.request(source, "GET", url, params=params)

    async def get_text(self, source: str, url: str, params: dict[str, Any] | None = None) -> str:
        return await self.request(source, "GET", url, params=params, expect="text")

    async def post_json(self, source: str, url: str, body: Any) -> Any:
        return await self.request(source, "POST", url, json_body=body)


def _retry_after_seconds(response: httpx.Response) -> float | None:
    value = response.headers.get("Retry-After")
    if value and value.isdigit():
        return min(float(value), 10.0)
    return None
