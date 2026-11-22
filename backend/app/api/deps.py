"""FastAPI dependencies: shared services and the (optional) authenticated user."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status

from app.config import Settings
from app.integrations.http import SourceHttpClient
from app.services.auth import AuthError, AuthUser, SupabaseAuthVerifier
from app.services.repository import SessionRepository
from app.services.research_service import ResearchService


@dataclass
class Services:
    settings: Settings
    repo: SessionRepository
    research: ResearchService
    auth: SupabaseAuthVerifier
    http: SourceHttpClient


def get_services(request: Request) -> Services:
    return request.app.state.services


ServicesDep = Annotated[Services, Depends(get_services)]


async def get_optional_user(request: Request, services: ServicesDep) -> AuthUser | None:
    header = request.headers.get("Authorization", "")
    if not header:
        return None
    scheme, _, token = header.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Malformed Authorization header")
    try:
        return await services.auth.verify(token)
    except AuthError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, str(exc)) from exc


OptionalUser = Annotated[AuthUser | None, Depends(get_optional_user)]


def client_key(request: Request) -> str:
    """Best-effort client identifier for anonymous rate limiting (Render sets X-Forwarded-For)."""
    forwarded = request.headers.get("X-Forwarded-For", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"
