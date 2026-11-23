"""ClinicalTrials.gov API v2.

Docs: https://clinicaltrials.gov/data-api/about-api
A registered trial documents that a study exists; it is not evidence that an intervention works.
"""

from __future__ import annotations

import logging
from typing import Any

from app.integrations._parsing import clean_text, date_from_text, truncate
from app.integrations.http import SourceError, SourceHttpClient
from app.integrations.paging import PAGE_SIZE, SearchPage, as_int
from app.integrations.provenance import make_provenance
from app.models.evidence import EvidenceCategory, EvidenceRecord, EvidenceType, Identifiers, SourceName

logger = logging.getLogger(__name__)

STUDIES_URL = "https://clinicaltrials.gov/api/v2/studies"
SOURCE = SourceName.CLINICAL_TRIALS.value

STOPPED_STATUSES = {"TERMINATED", "WITHDRAWN", "SUSPENDED"}


async def search_clinical_trials(
    http: SourceHttpClient,
    *,
    condition: str | None,
    intervention: str | None = None,
    term: str | None = None,
    max_results: int = 20,
) -> list[EvidenceRecord]:
    page = await search_clinical_trials_paged(
        http, condition=condition, intervention=intervention, term=term, max_results=max_results
    )
    return page.records


async def search_clinical_trials_paged(
    http: SourceHttpClient,
    *,
    condition: str | None,
    intervention: str | None = None,
    term: str | None = None,
    max_results: int = 20,
    start_from: int | None = None,
    start_to: int | None = None,
    page_size: int = PAGE_SIZE,
) -> SearchPage:
    """Relevance-ranked study search, paged with `pageToken`. Optional filter on study start year."""
    described = "; ".join(
        f"{k}: {v}"
        for k, v in (("condition", condition), ("intervention", intervention), ("terms", term))
        if v
    )
    page = SearchPage(query=described)
    if not (condition or intervention or term):
        return page
    base: dict[str, str | int] = {"format": "json", "countTotal": "true"}
    if condition:
        base["query.cond"] = condition
    if intervention:
        base["query.intr"] = intervention
    if term:
        base["query.term"] = term
    if start_from or start_to:
        lo = f"{start_from}-01-01" if start_from else "MIN"
        hi = f"{start_to}-12-31" if start_to else "MAX"
        base["filter.advanced"] = f"AREA[StartDate]RANGE[{lo},{hi}]"
        page.query += f"; start date {lo} to {hi}"
    token: str | None = None
    while len(page.records) < max_results:
        size = min(page_size, max_results - len(page.records))
        params = {**base, "pageSize": size}
        if token:
            params["pageToken"] = token
        data = await http.get_json(SOURCE, STUDIES_URL, params)
        batch = parse_studies(data)
        page.pages += 1
        if page.total_available is None:
            page.total_available = as_int(data.get("totalCount"))
        page.records.extend(batch)
        token = data.get("nextPageToken")
        if len(data["studies"]) < size or not token:
            break
    page.records = page.records[:max_results]
    return page


def parse_studies(data: Any) -> list[EvidenceRecord]:
    if not isinstance(data, dict) or not isinstance(data.get("studies"), list):
        raise SourceError(SOURCE, "unexpected studies response shape")
    records = []
    for study in data["studies"]:
        try:
            record = _parse_study(study)
        except Exception:
            logger.warning("clinical_trials_parse_skip reason=malformed_study", exc_info=True)
            continue
        if record:
            records.append(record)
    return records


def _outcomes(proto: dict[str, Any], key: str, limit: int = 5) -> list[dict[str, str]]:
    """Registered outcome *measures* (what the trial plans to measure), not outcome results."""
    out = []
    for o in ((proto.get("outcomesModule") or {}).get(key) or [])[:limit]:
        measure = clean_text(o.get("measure"))
        if measure:
            out.append(
                {
                    "measure": truncate(measure, 300),
                    "time_frame": truncate(clean_text(o.get("timeFrame")) or "", 120),
                }
            )
    return out


def _humanise(value: str | None) -> str | None:
    return value.replace("_", " ").title() if value else None


def _parse_study(study: dict[str, Any]) -> EvidenceRecord | None:
    proto = study.get("protocolSection") or {}
    ident = proto.get("identificationModule") or {}
    nct_id = ident.get("nctId")
    title = ident.get("briefTitle") or ident.get("officialTitle")
    if not nct_id or not title:
        return None

    status = proto.get("statusModule") or {}
    design = proto.get("designModule") or {}
    design_info = design.get("designInfo") or {}
    conditions = (proto.get("conditionsModule") or {}).get("conditions") or []
    interventions = [
        {"name": i.get("name"), "type": _humanise(i.get("type"))}
        for i in (proto.get("armsInterventionsModule") or {}).get("interventions") or []
        if i.get("name")
    ]
    sponsor = ((proto.get("sponsorCollaboratorsModule") or {}).get("leadSponsor") or {}).get("name")
    start = (status.get("startDateStruct") or {}).get("date")
    completion_struct = status.get("completionDateStruct") or status.get("primaryCompletionDateStruct") or {}
    overall_status = status.get("overallStatus")
    phases = [
        p.replace("PHASE", "Phase ").replace("EARLY_", "Early ").strip() for p in design.get("phases") or []
    ]

    return EvidenceRecord(
        record_id=f"clinicaltrials_gov:{nct_id}",
        source_name=SourceName.CLINICAL_TRIALS,
        source_identifier=nct_id,
        category=EvidenceCategory.CLINICAL_TRIAL,
        evidence_type=EvidenceType.CLINICAL_TRIAL,
        title=clean_text(title) or nct_id,
        summary=truncate(clean_text((proto.get("descriptionModule") or {}).get("briefSummary")), 1500),
        source_url=f"https://clinicaltrials.gov/study/{nct_id}",
        provenance=make_provenance("clinical_trials", f"{STUDIES_URL}/{nct_id}", study),
        publication_date=date_from_text(start),
        identifiers=Identifiers(nct_id=nct_id),
        metadata={
            "overall_status": overall_status,
            "status_label": _humanise(overall_status),
            "phases": [p for p in phases if p and p != "NA"],
            "study_type": _humanise(design.get("studyType")),
            "allocation": _humanise(design_info.get("allocation")),
            "masking": _humanise((design_info.get("maskingInfo") or {}).get("masking")),
            "primary_purpose": _humanise(design_info.get("primaryPurpose")),
            "enrollment": (design.get("enrollmentInfo") or {}).get("count"),
            # ACTUAL or ESTIMATED: an estimated enrolment is a target, not a participant count.
            "enrollment_type": _humanise((design.get("enrollmentInfo") or {}).get("type")),
            "primary_outcomes": _outcomes(proto, "primaryOutcomes"),
            "secondary_outcome_count": len(
                (proto.get("outcomesModule") or {}).get("secondaryOutcomes") or []
            ),
            "conditions": conditions,
            "interventions": interventions,
            "lead_sponsor": sponsor,
            "start_date": start,
            "completion_date": completion_struct.get("date"),
            "completion_date_type": _humanise(completion_struct.get("type")),
            "has_results": bool(study.get("hasResults")),
            "why_stopped": status.get("whyStopped"),
            "last_update": (status.get("lastUpdatePostDateStruct") or {}).get("date"),
        },
    )
