"""Supabase Auth token verification (server-side). Never trusts a user id supplied by the browser."""

from __future__ import annotations

import hashlib
import logging
import time
from dataclasses import dataclass

import httpx

from app.config import Settings

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class AuthUser:
    id: str
    email: str | None


class AuthError(Exception):
    pass


class SupabaseAuthVerifier:
    """Validates an access token by asking Supabase Auth who it belongs to (`GET /auth/v1/user`).

    Results are cached briefly (keyed by a hash of the token) to avoid a round trip on every poll.
    """

    def __init__(
        self, settings: Settings, client: httpx.AsyncClient | None = None, ttl_seconds: float = 60
    ) -> None:
        self._url = (settings.supabase_url or "").rstrip("/")
        key = settings.supabase_anon_key or settings.supabase_service_role_key
        self._apikey = key.get_secret_value() if key else ""
        self._client = client or httpx.AsyncClient(timeout=10)
        self._ttl = ttl_seconds
        self._cache: dict[str, tuple[float, AuthUser]] = {}

    @property
    def enabled(self) -> bool:
        return bool(self._url and self._apikey)

    async def verify(self, token: str) -> AuthUser:
        if not self.enabled:
            raise AuthError("authentication is not configured")
        digest = hashlib.sha256(token.encode()).hexdigest()
        hit = self._cache.get(digest)
        if hit and hit[0] > time.monotonic():
            return hit[1]
        try:
            resp = await self._client.get(
                f"{self._url}/auth/v1/user",
                headers={"Authorization": f"Bearer {token}", "apikey": self._apikey},
            )
        except httpx.HTTPError as exc:
            logger.warning("auth_verify_unreachable error=%s", type(exc).__name__)
            raise AuthError("could not verify session") from exc
        if resp.status_code != 200:
            raise AuthError("invalid or expired session")
        data = resp.json()
        user = AuthUser(id=data["id"], email=data.get("email"))
        self._cache[digest] = (time.monotonic() + self._ttl, user)
        return user

    async def aclose(self) -> None:
        await self._client.aclose()
