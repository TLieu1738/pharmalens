"""Research Synthesis agent: the LLM writes a structured briefing over the validated evidence only.

After generation, every citation is checked against the retrieved record IDs. Invalid citations are removed,
and any "finding" left without a valid citation is dropped. References are built deterministically.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from app.agents.llm import StructuredLLM
from app.models.evidence import EvidenceRecord
from app.models.report import (
    REPORT_SECTIONS,
    Reference,
    ReportIntegrity,
    ReportSection,
    ResearchReport,
    Statement,
    StatementKind,
    SynthesisOutput,
)
from app.models.research import ResearchPlan

MAX_RECORDS_IN_PROMPT = 90
SUMMARY_CHARS = 700

SYSTEM_PROMPT = """You are the Research Synthesis agent in PharmaLens, a research-support tool for \
biomedical researchers. You write a structured evidence briefing using ONLY the evidence records provided \
in <evidence>. You have no other sources.

Rules for scientific integrity:
- Every statement of kind "finding" must cite one or more record_id values from <evidence> that directly \
support it. Cite exact record_id strings. Never invent identifiers, results, statistics, trial outcomes or URLs.
- Use kind "hypothesis" for reasonable inferences that the records do not establish, and phrase them \
tentatively. Use kind "gap" for open questions or missing evidence. These may cite records that motivate them.
- Only state what the record text says. Abstracts are summaries, not full papers; database entries are \
annotations. Do not overstate: a registered or ongoing trial is not evidence of efficacy; an Open Targets \
association is not proof of causation; a ChEMBL development phase refers to any indication, not necessarily \
the one in the question; preprints are not peer reviewed.
- Distinguish approved medicines, investigational compounds, preclinical findings, clinical-trial results, \
reviews and preprints explicitly when relevant.
- Never recommend treatments or doses for patients. Never describe synthesis, formulation or manufacturing.
- If a section has little or no supporting evidence, say so in a "gap" statement rather than filling it in.

Style: precise, neutral, for a scientific audience. Each statement is 1-2 sentences of plain text with no \
citation markers or markdown inside the text (citations go in the citations array). Aim for 3-6 statements \
per section and 3-5 in the executive summary."""


def _record_digest(record: EvidenceRecord) -> dict[str, Any]:
    md = record.metadata
    digest: dict[str, Any] = {
        "record_id": record.record_id,
        "source": record.source_name.value,
        "evidence_type": record.evidence_type.value,
        "title": record.title,
        "date": record.publication_date,
    }
    if record.journal:
        digest["journal"] = record.journal
    if record.quality_flags:
        digest["flags"] = [f.value for f in record.quality_flags]
    if record.category.value == "clinical_trial":
        digest.update(
            {
                k: md.get(k)
                for k in (
                    "status_label",
                    "phases",
                    "study_type",
                    "allocation",
                    "enrollment",
                    "conditions",
                    "lead_sponsor",
                    "has_results",
                    "why_stopped",
                )
                if md.get(k) not in (None, [], "")
            }
        )
        digest["interventions"] = [i["name"] for i in md.get("interventions", [])][:6]
    elif record.category.value == "compound":
        digest.update(
            {
                k: md.get(k)
                for k in ("molecule_type", "max_phase_label", "first_approval", "withdrawn")
                if md.get(k) not in (None, "")
            }
        )
        digest["mechanisms"] = [m["mechanism_of_action"] for m in md.get("mechanisms", [])]
    elif record.category.value == "target":
        digest.update(
            {
                k: md.get(k)
                for k in (
                    "target_symbol",
                    "disease_name",
                    "association_rank",
                    "association_score",
                    "datatype_scores",
                )
            }
        )
    if record.summary and record.category.value in ("literature", "clinical_trial"):
        digest["summary"] = record.summary[:SUMMARY_CHARS]
    return digest


def build_prompt(
    question: str, plan: ResearchPlan, records: list[EvidenceRecord], profile: dict[str, Any]
) -> str:
    digests = [_record_digest(r) for r in records[:MAX_RECORDS_IN_PROMPT]]
    return (
        f"<research_question>\n{question}\n</research_question>\n\n"
        f"<research_plan>\n{plan.model_dump_json(include={'disease_area', 'biological_targets', 'compounds', 'objectives'})}\n</research_plan>\n\n"
        f"<evidence_profile>\n{json.dumps(profile)}\n</evidence_profile>\n\n"
        f"<evidence>\n" + "\n".join(json.dumps(d, ensure_ascii=False) for d in digests) + "\n</evidence>\n\n"
        "Write the briefing now, following the rules."
    )


def ground_report(
    output: SynthesisOutput,
    records: list[EvidenceRecord],
    *,
    question: str,
    scope: str,
    model: str,
) -> ResearchReport:
    """Enforce citation integrity and build references from real records only."""
    by_id = {r.record_id: r for r in records}
    total = removed_statements = removed_citations = findings_cited = 0
    order: list[str] = []
    sections: list[ReportSection] = []

    for key, title in REPORT_SECTIONS:
        kept: list[Statement] = []
        for st in getattr(output, key):
            total += 1
            valid = [c for c in dict.fromkeys(st.citations) if c in by_id]
            removed_citations += len(set(st.citations)) - len(valid)
            if st.kind == StatementKind.FINDING and not valid:
                removed_statements += 1
                continue
            if st.kind == StatementKind.FINDING:
                findings_cited += 1
            order.extend(c for c in valid if c not in order)
            kept.append(Statement(text=st.text.strip(), kind=st.kind, citations=valid))
        sections.append(ReportSection(key=key, title=title, statements=kept))

    references = [
        Reference(
            number=i,
            record_id=rid,
            title=by_id[rid].title,
            source_name=by_id[rid].source_name,
            evidence_type=by_id[rid].evidence_type,
            source_url=str(by_id[rid].source_url),
            publication_date=by_id[rid].publication_date,
            retrieved_at=by_id[rid].retrieved_at,
        )
        for i, rid in enumerate(order, start=1)
    ]
    return ResearchReport(
        research_question=question,
        scope=scope,
        sections=sections,
        references=references,
        integrity=ReportIntegrity(
            statements_total=total,
            statements_removed_unsupported=removed_statements,
            citations_removed_invalid=removed_citations,
            findings_with_citations=findings_cited,
        ),
        model=model,
        generated_at=datetime.now(UTC),
    )


def describe_scope(plan: ResearchPlan, profile: dict[str, Any], failed_sources: list[str]) -> str:
    sources = ", ".join(sorted(profile.get("by_source", {}))) or "none"
    years = profile.get("publication_year_range")
    text = (
        f"Disease area: {plan.disease_area or 'not specified'}. Literature query: {plan.literature_query}. "
        f"{profile.get('total_records', 0)} unique records retrieved from: {sources}"
        f" ({profile.get('duplicates_removed', 0)} cross-source duplicates merged)."
    )
    if years:
        text += f" Dated records span {years[0]}–{years[1]}."
    if failed_sources:
        text += f" Unavailable during this run: {', '.join(failed_sources)}."
    text += " Retrieval is limited to top-ranked results per source and is not a systematic review."
    return text


async def synthesise_report(
    llm: StructuredLLM,
    *,
    question: str,
    plan: ResearchPlan,
    records: list[EvidenceRecord],
    profile: dict[str, Any],
    failed_sources: list[str],
    model_name: str,
) -> ResearchReport:
    output = await llm.structured(
        system=SYSTEM_PROMPT,
        prompt=build_prompt(question, plan, records, profile),
        output=SynthesisOutput,
        effort="medium",
        max_tokens=16000,
    )
    return ground_report(
        output,
        records,
        question=question,
        scope=describe_scope(plan, profile, failed_sources),
        model=model_name,
    )
