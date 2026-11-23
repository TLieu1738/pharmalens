"""FastAPI application entrypoint."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.agents.llm import StructuredLLM
from app.api.deps import Services
from app.api.routes import graph, health, library, research, sessions
from app.config import APP_VERSION, Settings, get_settings
from app.integrations.http import SourceHttpClient
from app.logging_config import configure_logging
from app.models.health import RootResponse
from app.services.auth import SupabaseAuthVerifier
from app.services.repository import InMemorySessionRepository, SessionRepository
from app.services.research_service import JobRunner, ResearchService

logger = logging.getLogger("pharmalens")


def build_repository(settings: Settings) -> SessionRepository:
    if settings.supabase_configured:
        from app.services.supabase_repository import SupabaseSessionRepository

        return SupabaseSessionRepository(settings)
    logger.warning("supabase_not_configured using in-memory session storage (not durable)")
    return InMemorySessionRepository()


def create_app(
    *,
    settings: Settings | None = None,
    repo: SessionRepository | None = None,
    llm: StructuredLLM | None = None,
    http: SourceHttpClient | None = None,
) -> FastAPI:
    settings = settings or get_settings()
    configure_logging()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        source_http = http or SourceHttpClient(timeout=settings.http_timeout_seconds)
        repository = repo or build_repository(settings)
        research = ResearchService(settings, repository, source_http, llm)
        services = Services(
            settings=settings,
            repo=repository,
            research=research,
            auth=SupabaseAuthVerifier(settings),
            http=source_http,
        )
        app.state.services = services
        runner = (
            JobRunner(settings, repository, source_http, research) if settings.run_worker_in_api else None
        )
        runner_task = asyncio.create_task(runner.run_forever(), name="job-runner") if runner else None
        logger.info(
            "startup environment=%s storage=%s cors_origins=%s",
            settings.environment,
            "supabase" if repository.durable else "memory",
            settings.cors_origins,
        )
        yield
        if runner and runner_task:
            runner_task.cancel()
            await asyncio.gather(runner_task, return_exceptions=True)
            await runner.shutdown()
        await services.auth.aclose()
        if http is None:
            await source_http.aclose()

    app = FastAPI(
        title=settings.app_name,
        version=APP_VERSION,
        description="Agentic research intelligence over public biomedical evidence.",
        docs_url="/docs" if settings.environment != "production" else None,
        redoc_url=None,
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type"],
    )

    @app.exception_handler(RequestValidationError)
    async def validation_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        # Return concise, user-facing messages (without echoing raw input back).
        messages = [str(e.get("msg", "Invalid input")).removeprefix("Value error, ") for e in exc.errors()]
        return JSONResponse(status_code=422, content={"detail": "; ".join(messages)})

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("unhandled_error path=%s", request.url.path)
        return JSONResponse(status_code=500, content={"detail": "Internal server error"})

    @app.get("/", response_model=RootResponse, tags=["meta"])
    async def root() -> RootResponse:
        return RootResponse(name=settings.app_name, status="running", version=APP_VERSION)

    app.include_router(health.router)
    app.include_router(research.router)
    app.include_router(sessions.router)
    app.include_router(library.router)
    app.include_router(graph.router)
    return app


app = create_app()
