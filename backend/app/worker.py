"""Standalone research worker: `python -m app.worker`.

Runs the same job loop as the API's built-in runner, for deployments that separate the web service from
long-running research (set RUN_WORKER_IN_API=false on the web service). Needs Supabase: jobs are claimed
from the shared database, so any number of workers can run side by side.
"""

from __future__ import annotations

import asyncio
import logging

from app.config import get_settings
from app.integrations.http import SourceHttpClient
from app.logging_config import configure_logging
from app.main import build_repository
from app.services.research_service import JobRunner, ResearchService

logger = logging.getLogger("pharmalens.worker")


async def main() -> None:
    configure_logging()
    settings = get_settings()
    if not settings.supabase_configured:
        raise SystemExit(
            "A separate worker needs Supabase configured (jobs are shared through the database)."
        )
    http = SourceHttpClient(timeout=settings.http_timeout_seconds)
    repo = build_repository(settings)
    runner = JobRunner(settings, repo, http, ResearchService(settings, repo, http))
    try:
        await runner.run_forever()
    finally:
        await runner.shutdown()
        await http.aclose()


if __name__ == "__main__":
    asyncio.run(main())
