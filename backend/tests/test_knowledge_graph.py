"""Knowledge graph: edges only where a record states the relationship, each carrying that record's ID."""

from fastapi.testclient import TestClient

from app.integrations.provenance import make_provenance
from app.models.evidence import EvidenceCategory, EvidenceRecord, EvidenceType, Identifiers, SourceName
from app.services.knowledge_graph import build_graph, normalise_name
from tests.test_api_research import QUESTION, wait_for_terminal


def rec(
    source: SourceName, ident: str, category: EvidenceCategory, title: str, **kw: object
) -> EvidenceRecord:
    return EvidenceRecord(
        record_id=f"{source.value}:{ident}",
        source_name=source,
        source_identifier=ident,
        category=category,
        evidence_type=EvidenceType.DATABASE_RECORD,
        title=title,
        source_url="https://example.org/x",
        provenance=make_provenance("test", "https://example.org/api", {}),
        **kw,  # type: ignore[arg-type]
    )


def records() -> list[EvidenceRecord]:
    target = rec(
        SourceName.OPEN_TARGETS,
        "MONDO_0004975:ENSG00000142192",
        EvidenceCategory.TARGET,
        "APP — amyloid beta precursor protein",
        identifiers=Identifiers(ensembl_id="ENSG00000142192"),
        metadata={
            "disease_id": "MONDO_0004975",
            "disease_name": "Alzheimer disease",
            "target_symbol": "APP",
            "target_name": "amyloid beta precursor protein",
            "association_score": 0.81,
        },
    )
    compound = rec(
        SourceName.CHEMBL,
        "CHEMBL3833321",
        EvidenceCategory.COMPOUND,
        "Lecanemab",
        metadata={
            "query": "lecanemab",
            "synonyms": ["BAN2401", "BAN-2401"],
            "max_phase": 4.0,
            "mechanisms": [
                {
                    "mechanism_of_action": "Amyloid-beta A4 protein inhibitor",
                    "target_chembl_id": "CHEMBL2487",
                    "target_gene_symbols": ["APP"],
                }
            ],
        },
    )
    pubchem = rec(
        SourceName.PUBCHEM,
        "3152",
        EvidenceCategory.COMPOUND,
        "Donepezil",
        metadata={"linked_chembl_id": "CHEMBL502"},  # no such ChEMBL compound in this set
    )
    trial = rec(
        SourceName.CLINICAL_TRIALS,
        "NCT01767311",
        EvidenceCategory.CLINICAL_TRIAL,
        "A Study of BAN2401 in Early Alzheimer's Disease",
        metadata={
            "conditions": ["Alzheimer's Disease"],
            "interventions": [
                {"name": "Lecanemab 10 mg/kg", "type": "Drug"},
                {"name": "Placebo", "type": "Drug"},
                {"name": "Aducanumab", "type": "Drug"},  # not a retrieved compound: no edge
            ],
            "lead_sponsor": "Eisai Inc.",
        },
    )
    paper = rec(
        SourceName.PUBMED,
        "36449413",
        EvidenceCategory.LITERATURE,
        "Lecanemab in Early Alzheimer's Disease",
        summary="Results of the CLARITY AD trial (NCT03887455) and the core study NCT01767311.",
    )
    unrelated = rec(
        SourceName.EUROPE_PMC,
        "MED:1",
        EvidenceCategory.LITERATURE,
        "Microglia in neurodegeneration",
        summary="No drug.",
    )
    return [target, compound, pubchem, trial, paper, unrelated]


def test_edges_are_only_those_stated_by_records() -> None:
    graph = build_graph(records())
    edges = {(e.source, e.relation, e.target): e for e in graph.edges}
    assert set(edges) == {
        ("target:APP", "associated_with", "disease:alzheimer disease"),
        ("compound:CHEMBL3833321", "acts_on", "target:APP"),
        ("trial:NCT01767311", "tests", "compound:CHEMBL3833321"),
        ("trial:NCT01767311", "studies", "disease:alzheimer disease"),
        ("trial:NCT01767311", "sponsored_by", "sponsor:eisai inc"),
        ("publication:pubmed:36449413", "references", "trial:NCT01767311"),
        ("publication:pubmed:36449413", "mentions", "compound:CHEMBL3833321"),
    }
    assert edges[("trial:NCT01767311", "tests", "compound:CHEMBL3833321")].record_ids == [
        "clinicaltrials_gov:NCT01767311",
        "chembl:CHEMBL3833321",
    ]
    assert edges[("target:APP", "associated_with", "disease:alzheimer disease")].detail == (
        "Open Targets association score 0.81"
    )


def test_nodes_merge_only_on_shared_identifiers_and_every_edge_is_traceable() -> None:
    data = records()
    graph = build_graph(data)
    ids = {r.record_id for r in data}
    nodes = {n.id: n for n in graph.nodes}
    # One APP node from both Open Targets and ChEMBL (same HGNC symbol); one disease node for both spellings.
    assert sum(1 for n in graph.nodes if n.type == "target") == 1
    assert sum(1 for n in graph.nodes if n.type == "disease") == 1
    assert all(e.record_ids and set(e.record_ids) <= ids for e in graph.edges)
    assert all(set(n.record_ids) <= ids for n in graph.nodes)
    # Unlinked paper and the PubChem record without its ChEMBL compound produce no nodes; NCT03887455
    # was not retrieved, so no trial node is invented for it.
    assert "publication:europe_pmc:MED:1" not in nodes and "trial:NCT03887455" not in nodes
    assert all("pubchem:3152" not in n.record_ids for n in graph.nodes)
    assert graph.stats["publications_without_links"] == 1


def test_pubchem_record_attaches_to_its_chembl_compound() -> None:
    data = records()
    data[2].metadata["linked_chembl_id"] = "CHEMBL3833321"
    nodes = {n.id: n for n in build_graph(data).nodes}
    compound = nodes["compound:CHEMBL3833321"]
    assert compound.data["pubchem_cid"] == "3152" and "pubchem:3152" in compound.record_ids


def test_name_normalisation() -> None:
    assert normalise_name("Alzheimer's Disease") == normalise_name("Alzheimer disease") == "alzheimer disease"


def test_graph_endpoint_is_private(research_client: TestClient) -> None:
    alice = {"Authorization": "Bearer token-alice"}
    bob = {"Authorization": "Bearer token-bob"}
    sid = research_client.post("/api/research", json={"research_question": QUESTION}, headers=alice).json()[
        "session_id"
    ]
    wait_for_terminal(research_client, sid, alice)

    graph = research_client.get("/api/graph", headers=alice).json()
    assert graph["nodes"] and graph["edges"]
    assert (
        research_client.get(f"/api/graph?session_id={sid}", headers=alice).json()["edges"] == graph["edges"]
    )
    assert research_client.get("/api/graph", headers=bob).json()["nodes"] == []
    assert research_client.get(f"/api/graph?session_id={sid}", headers=bob).status_code == 404
    assert research_client.get("/api/graph").status_code == 401
