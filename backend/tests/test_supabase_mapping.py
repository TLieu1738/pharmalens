from app.integrations.pubmed import parse_pubmed_xml
from app.models.evidence import QualityFlag, SourceName
from app.services.supabase_repository import _evidence_to_row, _row_to_evidence
from tests.helpers import fixture_text


def test_evidence_row_round_trip_preserves_record() -> None:
    record = parse_pubmed_xml(fixture_text("pubmed_efetch.xml"))[0]
    record.quality_flags = [QualityFlag.ABSTRACT_ONLY]
    record.also_found_in = [SourceName.EUROPE_PMC]
    row = _evidence_to_row("sid", 3, record)
    assert row["position"] == 3 and row["source_url"] == "https://pubmed.ncbi.nlm.nih.gov/39776249/"
    restored = _row_to_evidence(row)
    assert restored == record
