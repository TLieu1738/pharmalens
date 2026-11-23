import pytest
from pydantic import ValidationError

from app.models.research import ResearchPlan, ResearchRequest


def test_question_is_normalised() -> None:
    req = ResearchRequest(research_question="  Investigate\n\n tau   biology in Alzheimer's disease\x00  ")
    assert req.research_question == "Investigate tau biology in Alzheimer's disease"


@pytest.mark.parametrize("question", ["", "   ", "too short", "x" * 2001])
def test_invalid_questions_rejected(question: str) -> None:
    with pytest.raises(ValidationError):
        ResearchRequest(research_question=question)


def test_plan_defaults_to_all_sources() -> None:
    plan = ResearchPlan(literature_query="alzheimer tau")
    assert len(plan.sources) == 7
