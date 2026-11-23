import uuid

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel

from app.api.deps import OptionalUser, ServicesDep, client_key
from app.models.evidence import EvidenceRecord
from app.models.research import (
    TERMINAL_STATUSES,
    ResearchCreatedResponse,
    ResearchPlan,
    SessionStatus,
    SessionSummary,
)
from app.models.session import SessionDetail
from app.services.research_service import CapacityError, ServiceUnavailableError

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


async def _editable_session(session_id: str, services: ServicesDep, user: OptionalUser) -> SessionDetail:
    """Only the owner may change a session (anonymous demo sessions: whoever holds the link)."""
    detail = await _authorised_session(session_id, services, user)
    if not detail.is_owner and not detail.demo_mode:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Session not found")
    return detail


class ApproveRequest(BaseModel):
    protocol: ResearchPlan | None = None  # omitted = approve the protocol as currently saved


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


@router.put("/{session_id}/protocol", response_model=ResearchPlan)
async def update_protocol(
    session_id: str, protocol: ResearchPlan, services: ServicesDep, user: OptionalUser
) -> ResearchPlan:
    """Save edits to a drafted protocol. Only possible before approval."""
    detail = await _editable_session(session_id, services, user)
    if not await services.repo.update_plan(detail.session_id, protocol):
        raise HTTPException(
            status.HTTP_409_CONFLICT, "The protocol can only be edited while it awaits approval."
        )
    return protocol


@router.post("/{session_id}/approve", response_model=SessionDetail)
async def approve_protocol(
    session_id: str, body: ApproveRequest, services: ServicesDep, user: OptionalUser
) -> SessionDetail:
    """Approve the protocol (optionally with final edits) and queue the research run."""
    detail = await _editable_session(session_id, services, user)
    protocol = body.protocol or detail.research_plan
    if protocol is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "There is no drafted protocol to approve yet.")
    if not await services.research.approve(detail.session_id, protocol):
        raise HTTPException(
            status.HTTP_409_CONFLICT, "This protocol has already been approved or the session ended."
        )
    return await _authorised_session(session_id, services, user)


@router.post("/{session_id}/cancel", response_model=SessionDetail)
async def cancel_session(session_id: str, services: ServicesDep, user: OptionalUser) -> SessionDetail:
    detail = await _editable_session(session_id, services, user)
    if detail.status in TERMINAL_STATUSES or not await services.repo.cancel(detail.session_id):
        raise HTTPException(status.HTTP_409_CONFLICT, "This research session has already finished.")
    return await _authorised_session(session_id, services, user)


@router.post(
    "/{session_id}/rerun", response_model=ResearchCreatedResponse, status_code=status.HTTP_201_CREATED
)
async def rerun_session(
    session_id: str, request: Request, services: ServicesDep, user: OptionalUser
) -> ResearchCreatedResponse:
    """Start a new session from this one's question and protocol, opened for editing before approval."""
    detail = await _editable_session(session_id, services, user)
    if detail.research_plan is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "This session has no protocol to reuse.")
    if user is None and not services.settings.demo_mode:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Sign in to run research.")
    try:
        new_id = await services.research.start(
            detail.research_question,
            user.id if user else None,
            client_key(request),
            plan=detail.research_plan,
        )
    except CapacityError as exc:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, str(exc)) from exc
    except ServiceUnavailableError as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(exc)) from exc
    return ResearchCreatedResponse(session_id=new_id, status=SessionStatus.AWAITING_APPROVAL)
