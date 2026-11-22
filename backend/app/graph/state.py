"""LangGraph state for a research session."""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from app.models.agents import AgentExecution
from app.models.evidence import EvidenceRecord
from app.models.report import ResearchReport
from app.models.research import ResearchPlan


def merge_dicts(left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
    return {**left, **right}


class ResearchState(TypedDict, total=False):
    session_id: str
    research_question: str
    research_plan: ResearchPlan | None
    literature_records: list[EvidenceRecord]
    clinical_records: list[EvidenceRecord]
    compound_records: list[EvidenceRecord]
    target_records: list[EvidenceRecord]
    validated_evidence: list[EvidenceRecord]
    evidence_profile: dict[str, Any]
    report: ResearchReport | None
    # Parallel branches write these concurrently, so they need reducers.
    agent_statuses: Annotated[dict[str, AgentExecution], merge_dicts]
    errors: Annotated[list[str], operator.add]
    warnings: Annotated[list[str], operator.add]
    failed_sources: Annotated[list[str], operator.add]
