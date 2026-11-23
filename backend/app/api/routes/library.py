"""Evidence library: every record retrieved across the signed-in user's research sessions."""

import asyncio
from datetime import datetime

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from app.api.deps import OptionalUser, ServicesDep
from app.models.evidence import EvidenceRecord

router = APIRouter(prefix="/api/library", tags=["library"])

MAX_SESSIONS = 50


class SessionRef(BaseModel):
    session_id: str
    research_question: str
    created_at: datetime


class LibraryRecord(EvidenceRecord):
    """An evidence record plus the sessions in which it was retrieved (deduplicated by `record_id`)."""

    sessions: list[SessionRef]


@router.get("", response_model=list[LibraryRecord])
async def get_library(services: ServicesDep, user: OptionalUser) -> list[LibraryRecord]:
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Sign in to view your evidence library.")
    summaries = await services.repo.list_sessions(user.id, limit=MAX_SESSIONS)
    evidence = await asyncio.gather(*(services.repo.get_evidence(s.session_id) for s in summaries))

    merged: dict[str, LibraryRecord] = {}
    for summary, records in zip(summaries, evidence, strict=True):
        ref = SessionRef(
            session_id=summary.session_id,
            research_question=summary.research_question,
            created_at=summary.created_at,
        )
        for record in records:
            existing = merged.get(record.record_id)
            if existing is None:
                # Sessions are newest-first, so the first copy seen is the most recent retrieval.
                merged[record.record_id] = LibraryRecord(**record.model_dump(), sessions=[ref])
            elif all(s.session_id != ref.session_id for s in existing.sessions):
                existing.sessions.append(ref)
    return list(merged.values())
