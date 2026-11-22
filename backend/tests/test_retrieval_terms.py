"""Query-term construction for the Clinical and Compound agents."""

import pytest

from app.agents.clinical import MAX_TRIAL_TERMS, _or_terms, trial_search_terms
from app.agents.compounds import normalise_intervention_name
from app.models.research import ResearchPlan


def test_trial_terms_include_named_compounds_before_class_terms():
    plan = ResearchPlan(
        literature_query="x",
        compounds=["lecanemab", "donanemab"],
        clinical_intervention_terms=["anti-amyloid antibody"],
        biological_targets=["tau"],
    )
    assert trial_search_terms(plan) == ["lecanemab", "donanemab", "anti-amyloid antibody"]
    assert _or_terms(trial_search_terms(plan)) == 'lecanemab OR donanemab OR "anti-amyloid antibody"'


def test_trial_terms_fall_back_to_targets():
    plan = ResearchPlan(literature_query="x", biological_targets=["tau", "APP", "BACE1", "PSEN1"])
    assert trial_search_terms(plan) == ["tau", "APP", "BACE1"]


def test_or_terms_dedupes_and_caps():
    terms = ["a", "a", " b "] + [f"t{i}" for i in range(20)]
    joined = _or_terms(terms)
    assert joined is not None
    parts = joined.split(" OR ")
    assert parts[:2] == ["a", "b"]
    assert len(parts) == MAX_TRIAL_TERMS
    assert _or_terms(["", "  "]) is None


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("AV-1980R", "AV-1980R"),
        ("LY3202626", "LY3202626"),
        ("Lecanemab 10 mg/kg IV", "Lecanemab"),
        ("Donanemab (LY3002813)", "Donanemab"),
        ("Gantenerumab - subcutaneous", "Gantenerumab"),
        ("Semorinemab 4500 mg", "Semorinemab"),
        ("DUVAX", "DUVAX"),
    ],
)
def test_normalise_intervention_name_keeps_code_names(raw, expected):
    assert normalise_intervention_name(raw) == expected


def test_unique_compound_queries_drops_repeats_and_arm_labels():
    from app.agents.compounds import unique_compound_queries

    names = ["Lecanemab", "lecanemab", "lecanemab treatment group", "AV-1980R", "donanemab"]
    assert unique_compound_queries(names) == ["Lecanemab", "AV-1980R", "donanemab"]
