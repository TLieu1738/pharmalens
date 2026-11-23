"""Research report schema.

`SynthesisOutput` is what the LLM must return (validated via structured outputs). It is then checked
against the retrieved evidence and converted into `ResearchReport`, whose references are computed
deterministically from the cited record IDs — the LLM never writes reference entries or URLs.
"""

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field

from app.models.evidence import EvidenceType, SourceName


class StatementKind(StrEnum):
    """Claim types. The first three are factual and must be supported by cited evidence to be published."""

    FINDING = "finding"  # a scientific finding stated by the cited records
    CLINICAL_OUTCOME = "clinical_outcome"  # a reported clinical result (efficacy, safety, endpoint data)
    COMPARATIVE = "comparative_analysis"  # a comparison across two or more cited records
    INTERPRETATION = "interpretation"  # the model's reading of cited evidence, labelled as such
    HYPOTHESIS = "hypothesis"  # plausible inference, explicitly not established
    GAP = "gap"  # open question / missing evidence


FACTUAL_KINDS = {StatementKind.FINDING, StatementKind.CLINICAL_OUTCOME, StatementKind.COMPARATIVE}


class ValidationStatus(StrEnum):
    SUPPORTED = "supported"  # cited records directly support the claim
    PARTIALLY_SUPPORTED = "partially_supported"  # published with a visible caveat
    NOT_VERIFIED = "not_verified"  # deterministic checks passed; semantic check unavailable
    NOT_APPLICABLE = "not_applicable"  # hypotheses and open questions are not verified as facts
    UNSUPPORTED = "unsupported"  # never published (audit only)
    CONTRADICTED = "contradicted"  # never published (audit only)


class CitationSupport(BaseModel):
    record_id: str
    verdict: str  # supports | partially_supports | irrelevant | contradicts | not_assessed


class ClaimDraft(BaseModel):
    """A claim as the synthesis model proposes it. Never published without verification."""

    text: str = Field(description="One or two sentences. No citation markers inside the text.")
    kind: StatementKind
    citations: list[str] = Field(
        description="record_id values from the provided evidence that directly support this statement."
    )
    limitations: list[str] = Field(
        description="Caveats specific to this claim (population, design, abstract only, registry data). May be empty."
    )


class Statement(BaseModel):
    """A published claim: text, type, citations that passed verification, and how it was validated."""

    text: str
    kind: StatementKind
    citations: list[str]
    limitations: list[str] = Field(default_factory=list)
    validation_status: ValidationStatus = ValidationStatus.NOT_VERIFIED
    validation_notes: list[str] = Field(default_factory=list)
    support: list[CitationSupport] = Field(default_factory=list)


class SynthesisOutput(BaseModel):
    executive_summary: list[ClaimDraft]
    biological_targets: list[ClaimDraft]
    compounds_and_interventions: list[ClaimDraft]
    literature_findings: list[ClaimDraft]
    clinical_trial_landscape: list[ClaimDraft]
    evidence_strengths: list[ClaimDraft]
    evidence_limitations: list[ClaimDraft]
    conflicting_evidence: list[ClaimDraft] = Field(
        description="Disagreements or inconclusive results between records; empty if none are detectable."
    )
    research_gaps: list[ClaimDraft]
    conclusions: list[ClaimDraft] = Field(
        description="2-4 cautious conclusions that follow from the cited findings."
    )


# Order and titles of the AI-written sections. The research question, approved protocol, methodology and data
# sources sections are generated deterministically from the session record, not by the model.
REPORT_SECTIONS: list[tuple[str, str]] = [
    ("executive_summary", "Executive summary"),
    ("literature_findings", "Key scientific findings"),
    ("biological_targets", "Biological target analysis"),
    ("compounds_and_interventions", "Compound and drug development analysis"),
    ("clinical_trial_landscape", "Clinical trial analysis"),
    ("evidence_strengths", "Evidence quality: strengths"),
    ("evidence_limitations", "Evidence quality: limitations"),
    ("conflicting_evidence", "Conflicting or inconclusive evidence"),
    ("research_gaps", "Research gaps"),
    ("conclusions", "Conclusions"),
]


class ReportSection(BaseModel):
    key: str
    title: str
    statements: list[Statement]


class Reference(BaseModel):
    number: int
    record_id: str
    title: str
    source_name: SourceName
    evidence_type: EvidenceType
    source_url: str
    publication_date: str | None = None
    retrieved_at: datetime


class RemovedStatement(BaseModel):
    """A model statement dropped (or relabelled) by verification, kept for the audit trail."""

    section: str
    text: str
    reason: str
    kind: str | None = None
    status: str = ValidationStatus.UNSUPPORTED.value
    citations: list[str] = Field(default_factory=list)


class ReportIntegrity(BaseModel):
    """Machine-checked facts about how well the report is grounded in retrieved evidence."""

    statements_total: int
    statements_removed_unsupported: int
    citations_removed_invalid: int
    findings_with_citations: int
    removed_statements: list[RemovedStatement] = Field(default_factory=list)
    invalid_citations: list[str] = Field(default_factory=list)
    records_provided: int | None = None  # validated records given to the synthesis model
    records_available: int | None = None
    # Set only by the claim-verification step; repositories refuse to publish a report without it.
    validated: bool = False
    semantic_check: str = "not_run"  # completed | unavailable | not_run
    status_counts: dict[str, int] = Field(default_factory=dict)
    relabelled: list[RemovedStatement] = Field(default_factory=list)  # interpretations turned into hypotheses


DISCLAIMER = (
    "This briefing was generated by an AI research-support tool from publicly available records retrieved "
    "at the time shown. It is informational only, may be incomplete or out of date, and summarises abstracts "
    "and database entries rather than full papers. It is not medical advice and must be verified by qualified "
    "researchers against the cited sources. A registered clinical trial does not establish efficacy, and a "
    "database association does not establish causation."
)


class ResearchReport(BaseModel):
    research_question: str
    scope: str
    sections: list[ReportSection]
    references: list[Reference]
    integrity: ReportIntegrity
    disclaimer: str = DISCLAIMER
    model: str
    generated_at: datetime


class ReportNotPublishableError(Exception):
    """A report reached publication without passing claim verification."""


def ensure_publishable(report: ResearchReport) -> None:
    """Last gate before persistence: no unverified report, and no unsupported factual claim, can be saved."""
    if not report.integrity.validated:
        raise ReportNotPublishableError("report has not been through claim verification")
    known = {r.record_id for r in report.references}
    for section in report.sections:
        for st in section.statements:
            if st.kind in FACTUAL_KINDS:
                if not st.citations:
                    raise ReportNotPublishableError(f"factual claim without citations in '{section.title}'")
                if st.validation_status in (ValidationStatus.UNSUPPORTED, ValidationStatus.CONTRADICTED):
                    raise ReportNotPublishableError(
                        f"{st.validation_status.value} claim in '{section.title}'"
                    )
            if any(c not in known for c in st.citations):
                raise ReportNotPublishableError(f"citation without a reference entry in '{section.title}'")
