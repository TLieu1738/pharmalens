from fastapi import APIRouter

from app.api.deps import ServicesDep
from app.config import APP_VERSION
from app.models.health import HealthResponse

router = APIRouter(prefix="/api", tags=["health"])


@router.get("/health", response_model=HealthResponse)
async def health(services: ServicesDep) -> HealthResponse:
    """Report service health and which integrations are configured. Never returns secret values."""
    settings = services.settings
    checks = {
        "anthropic": "configured" if settings.anthropic_configured else "missing",
        "supabase": "configured" if settings.supabase_configured else "missing",
    }
    storage = "durable" if services.repo.durable else "in_memory"
    status = "ok" if all(v == "configured" for v in checks.values()) else "degraded"
    return HealthResponse(
        status=status, environment=settings.environment, version=APP_VERSION, checks=checks, storage=storage
    )
