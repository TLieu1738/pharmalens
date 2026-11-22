from fastapi import APIRouter, HTTPException, Request, status

from app.api.deps import OptionalUser, ServicesDep, client_key
from app.models.research import ResearchCreatedResponse, ResearchRequest, SessionStatus
from app.services.research_service import CapacityError, ServiceUnavailableError

router = APIRouter(prefix="/api", tags=["research"])


@router.post("/research", response_model=ResearchCreatedResponse, status_code=status.HTTP_202_ACCEPTED)
async def create_research(
    body: ResearchRequest, request: Request, services: ServicesDep, user: OptionalUser
) -> ResearchCreatedResponse:
    """Create a research session and start the agent workflow in the background."""
    if user is None and not services.settings.demo_mode:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Sign in to run research.")
    try:
        session_id = await services.research.start(
            body.research_question, user.id if user else None, client_key(request)
        )
    except CapacityError as exc:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, str(exc)) from exc
    except ServiceUnavailableError as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(exc)) from exc
    return ResearchCreatedResponse(session_id=session_id, status=SessionStatus.PENDING)
