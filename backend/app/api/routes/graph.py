"""Knowledge graph over the signed-in user's evidence (all sessions, or one session)."""

import asyncio

from fastapi import APIRouter, HTTPException, Query, status

from app.api.deps import OptionalUser, ServicesDep
from app.api.routes.library import MAX_SESSIONS
from app.api.routes.sessions import _authorised_session
from app.models.evidence import EvidenceRecord
from app.services.knowledge_graph import KnowledgeGraph, build_graph

router = APIRouter(prefix="/api/graph", tags=["graph"])


@router.get("", response_model=KnowledgeGraph)
async def get_graph(
    services: ServicesDep, user: OptionalUser, session_id: str | None = Query(default=None)
) -> KnowledgeGraph:
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Sign in to view the knowledge graph.")
    if session_id:
        detail = await _authorised_session(session_id, services, user)
        return build_graph(await services.repo.get_evidence(detail.session_id))
    summaries = await services.repo.list_sessions(user.id, limit=MAX_SESSIONS)
    evidence = await asyncio.gather(*(services.repo.get_evidence(s.session_id) for s in summaries))
    merged: dict[str, EvidenceRecord] = {}
    for records in evidence:  # newest session first, so the most recent copy of a record wins
        for record in records:
            merged.setdefault(record.record_id, record)
    return build_graph(list(merged.values()))
