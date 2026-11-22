"""Map source publication-type labels to PharmaLens evidence types (shared by PubMed and Europe PMC)."""

from app.models.evidence import EvidenceType

_REVIEW = {"review", "systematic review", "meta-analysis", "review-article", "scoping review"}
_PREPRINT = {"preprint"}
_NON_RESEARCH = {
    "editorial",
    "comment",
    "letter",
    "news",
    "published erratum",
    "retraction of publication",
    "biography",
    "interview",
    "portrait",
    "congress",
}
_PRIMARY = {
    "journal article",
    "research-article",
    "clinical trial",
    "randomized controlled trial",
    "clinical trial, phase i",
    "clinical trial, phase ii",
    "clinical trial, phase iii",
    "clinical trial, phase iv",
    "observational study",
    "comparative study",
    "multicenter study",
    "case reports",
    "controlled clinical trial",
}


def classify_publication(pub_types: list[str], *, is_preprint: bool = False) -> EvidenceType:
    """Classify from source-provided publication types.

    Heuristic and conservative: review/preprint labels take precedence; commentary-style types
    map to UNKNOWN rather than being upgraded to primary research.
    """
    labels = {p.strip().lower() for p in pub_types}
    if is_preprint or labels & _PREPRINT:
        return EvidenceType.PREPRINT
    if labels & _REVIEW:
        return EvidenceType.REVIEW
    if labels & _NON_RESEARCH:
        return EvidenceType.UNKNOWN
    if labels & _PRIMARY:
        return EvidenceType.PRIMARY_RESEARCH
    return EvidenceType.UNKNOWN


def is_retracted(pub_types: list[str]) -> bool:
    return any(p.strip().lower() == "retracted publication" for p in pub_types)
