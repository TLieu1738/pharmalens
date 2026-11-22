import uuid

from fastapi import APIRouter, HTTPException, status

from app.api.deps import OptionalUser, ServicesDep
from app.models.evidence import EvidenceRecord
from app.models.research import SessionSummary
from app.models.session import SessionDetail

router = APIRouter(prefix="/api/sessions", tags=["sessions"])


def _valid_uuid(session_id: str) -> str:
    try:
        return str(uuid.UUID(session_id))
    except ValueError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Session not found") from exc


async def _authorised_session(session_id: str, services: ServicesDep, user: OptionalUser) -> SessionDetail:
    """Owned sessions are visible only to their owner; anonymous demo sessions to anyone holding the UUID."""
    found = await services.repo.get_session(_valid_uuid(session_id))
    if found is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Session not found")
    detail, owner_id = found
    if owner_id is not None and (user is None or user.id != owner_id):
        # 404 rather than 403 so session existence is not revealed.
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Session not found")
    detail.is_owner = owner_id is not None and user is not None and user.id == owner_id
    return detail


@router.get("", response_model=list[SessionSummary])
async def list_sessions(services: ServicesDep, user: OptionalUser) -> list[SessionSummary]:
    """The authenticated user's previous sessions."""
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Sign in to view saved research.")
    return await services.repo.list_sessions(user.id)


@router.get("/{session_id}", response_model=SessionDetail)
async def get_session(session_id: str, services: ServicesDep, user: OptionalUser) -> SessionDetail:
    return await _authorised_session(session_id, services, user)


@router.get("/{session_id}/evidence", response_model=list[EvidenceRecord])
async def get_session_evidence(
    session_id: str, services: ServicesDep, user: OptionalUser
) -> list[EvidenceRecord]:
    detail = await _authorised_session(session_id, services, user)
    return await services.repo.get_evidence(detail.session_id)
