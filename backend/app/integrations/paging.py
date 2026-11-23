"""Shared result type for paginated source searches."""

from __future__ import annotations

from dataclasses import dataclass, field

from app.models.evidence import EvidenceRecord

PAGE_SIZE = 50  # records per request; keeps individual calls small and polite to public APIs


@dataclass
class SearchPage:
    """Records from one query, plus what the source reported about coverage."""

    records: list[EvidenceRecord] = field(default_factory=list)
    total_available: int | None = None  # how many records match the query at the source
    pages: int = 0
    query: str = ""

    @property
    def truncated(self) -> bool:
        return self.total_available is not None and self.total_available > len(self.records)


def as_int(value: object) -> int | None:
    try:
        return int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
