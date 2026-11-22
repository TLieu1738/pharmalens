"""Research Planner agent: turns a natural-language question into a validated ResearchPlan (LLM)."""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.agents.llm import StructuredLLM
from app.models.evidence import SourceName
from app.models.research import ResearchPlan

SYSTEM_PROMPT = """You are the Research Planner in PharmaLens, a research-support tool that retrieves public \
biomedical evidence (PubMed, Europe PMC, ClinicalTrials.gov, ChEMBL, Open Targets) for researchers.

Your job is to interpret the user's research question and produce search parameters. You do NOT answer the \
question and you make no scientific claims. Everything you output is a search term or a restatement of the \
user's intent; downstream code queries the real databases with it.

Guidelines:
- disease_area: the main disease or research area in standard nomenclature (e.g. "Alzheimer disease"), or null.
- biological_targets: targets/pathways the user mentions or clearly implies, as written in plain language.
- target_gene_symbols: official HGNC gene symbols only for targets whose mapping is standard and unambiguous \
(e.g. tau -> MAPT, amyloid-beta -> APP). Leave out anything uncertain.
- compounds: drugs or compounds the user names. You may add up to 5 well-known compounds that are \
directly relevant to the question's mechanisms so their database records can be checked; these are search \
terms only and will be verified against ChEMBL. Use generic (INN) names.
- concepts, objectives: short phrases capturing what the user wants to learn.
- literature_query: a concise query that works in both PubMed and Europe PMC. Use AND / OR with parentheses, \
3-8 key terms, no field tags, e.g. (alzheimer disease) AND (amyloid beta OR tau).
- clinical_condition: the condition term for ClinicalTrials.gov, or null if no disease is involved.
- clinical_intervention_terms: 0-4 short terms (mechanism or drug class) to narrow trial searches.
- sources: the databases relevant to this question (default to all five unless one is clearly irrelevant).
- rationale: 1-2 sentences explaining the plan to the user.

If the request asks for synthesis, manufacturing, formulation or extraction procedures, or for individual \
treatment or dosing advice, do not plan for that part; state in the rationale that PharmaLens only \
summarises published evidence."""


class PlannerOutput(BaseModel):
    """Schema the LLM fills in. Kept simple for structured outputs; clipped into ResearchPlan afterwards."""

    disease_area: str | None
    biological_targets: list[str]
    target_gene_symbols: list[str]
    compounds: list[str]
    concepts: list[str]
    objectives: list[str]
    literature_query: str = Field(description="Query for PubMed and Europe PMC")
    clinical_condition: str | None
    clinical_intervention_terms: list[str]
    sources: list[SourceName]
    rationale: str


def _clip(items: list[str], n: int) -> list[str]:
    seen: dict[str, str] = {}
    for item in items:
        item = item.strip()
        if item and item.lower() not in seen:
            seen[item.lower()] = item
    return list(seen.values())[:n]


async def plan_research(llm: StructuredLLM, question: str) -> ResearchPlan:
    out = await llm.structured(
        system=SYSTEM_PROMPT,
        prompt=f"<research_question>\n{question}\n</research_question>",
        output=PlannerOutput,
        effort="low",
        max_tokens=4000,
    )
    query = out.literature_query.strip() or question[:200]
    return ResearchPlan(
        disease_area=(out.disease_area or "").strip() or None,
        biological_targets=_clip(out.biological_targets, 10),
        target_gene_symbols=[s.upper() for s in _clip(out.target_gene_symbols, 10)],
        compounds=_clip(out.compounds, 8),
        concepts=_clip(out.concepts, 10),
        objectives=_clip(out.objectives, 10),
        literature_query=query,
        clinical_condition=(out.clinical_condition or "").strip() or None,
        clinical_intervention_terms=_clip(out.clinical_intervention_terms, 4),
        sources=list(dict.fromkeys(out.sources)) or list(SourceName),
        rationale=out.rationale.strip(),
    )
