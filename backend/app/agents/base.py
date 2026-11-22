"""Shared result type for retrieval agents."""

from __future__ import annotations

import logging
from collections.abc import Awaitable
from dataclasses import dataclass, field

from app.integrations.http import SourceError
from app.models.agents import SourceOutcome
from app.models.evidence import EvidenceRecord

logger = logging.getLogger(__name__)


@dataclass
class RetrievalResult:
    records: list[EvidenceRecord] = field(default_factory=list)
    sources: list[SourceOutcome] = field(default_factory=list)
    message: str | None = None
    warnings: list[str] = field(default_factory=list)

    @property
    def all_failed(self) -> bool:
        return bool(self.sources) and not any(s.ok for s in self.sources)

    @property
    def any_failed(self) -> bool:
        return any(not s.ok for s in self.sources)


async def run_source(
    result: RetrievalResult, source: str, call: Awaitable[list[EvidenceRecord]]
) -> list[EvidenceRecord]:
    """Await a source call, recording success/failure on `result` instead of raising."""
    try:
        records = await call
    except SourceError as exc:
        logger.warning("source_failed source=%s error=%s", source, exc.message)
        result.sources.append(SourceOutcome(source=source, ok=False, error=exc.message))
        return []
    except Exception:  # unexpected parser/runtime bug: isolate it to this source
        logger.exception("source_unexpected_error source=%s", source)
        result.sources.append(SourceOutcome(source=source, ok=False, error="unexpected error"))
        return []
    result.sources.append(SourceOutcome(source=source, ok=True, record_count=len(records)))
    return records
