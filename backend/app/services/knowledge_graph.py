"""Knowledge graph built deterministically from retrieved evidence records.

Every edge exists only because a specific source record states it, and carries the IDs of those records:

    target   ─associated_with→ disease    Open Targets association record
    compound ─acts_on→         target     ChEMBL mechanism (target gene symbols as recorded by ChEMBL)
    trial    ─tests→           compound   trial intervention name equals the ChEMBL compound name or a synonym
    trial    ─studies→         disease    trial condition as registered
    trial    ─sponsored_by→    sponsor    trial lead sponsor as registered
    paper    ─references→      trial      the paper's title or abstract contains the trial's NCT number
    paper    ─mentions→        compound   the paper's title or abstract names the compound

Nothing is inferred from similarity, embeddings or an LLM. Nodes from different sources are merged only on
identifiers or names both sources state (HGNC gene symbol for targets; normalised condition / disease name;
standard InChIKey links a PubChem record to its ChEMBL compound).
"""

from __future__ import annotations

import re
from collections import Counter
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.agents.compounds import normalise_intervention_name
from app.models.evidence import EvidenceCategory, EvidenceRecord, SourceName

NodeType = Literal["disease", "target", "compound", "trial", "publication", "sponsor"]
Relation = Literal["associated_with", "acts_on", "tests", "studies", "sponsored_by", "references", "mentions"]

_NCT = re.compile(r"\bNCT\d{8}\b")
MAX_CONDITIONS_PER_TRIAL = 5
MIN_NAME_LENGTH = 5  # shorter compound names/synonyms are too ambiguous to match in free text


class GraphNode(BaseModel):
    id: str
    type: NodeType
    label: str
    record_ids: list[str] = Field(default_factory=list)
    url: str | None = None
    data: dict[str, Any] = Field(default_factory=dict)


class GraphEdge(BaseModel):
    id: str
    source: str
    target: str
    relation: Relation
    record_ids: list[str]
    detail: str | None = None


class KnowledgeGraph(BaseModel):
    nodes: list[GraphNode]
    edges: list[GraphEdge]
    stats: dict[str, Any]


def normalise_name(text: str) -> str:
    """'Alzheimer's Disease' and 'Alzheimer disease' → 'alzheimer disease'."""
    text = re.sub(r"['’]s\b", "", text.lower())
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


class _Builder:
    def __init__(self) -> None:
        self.nodes: dict[str, GraphNode] = {}
        self.edges: dict[str, GraphEdge] = {}

    def node(
        self, node_id: str, type_: NodeType, label: str, record_id: str | None = None, **kw: Any
    ) -> GraphNode:
        node = self.nodes.get(node_id)
        if node is None:
            node = self.nodes[node_id] = GraphNode(id=node_id, type=type_, label=label, **kw)
        elif kw.get("url") and not node.url:
            node.url = kw["url"]
        if record_id and record_id not in node.record_ids:
            node.record_ids.append(record_id)
        return node

    def edge(
        self, source: str, target: str, relation: Relation, record_ids: list[str], detail: str | None = None
    ) -> None:
        edge_id = f"{source}|{relation}|{target}"
        edge = self.edges.get(edge_id)
        if edge is None:
            self.edges[edge_id] = GraphEdge(
                id=edge_id,
                source=source,
                target=target,
                relation=relation,
                record_ids=list(record_ids),
                detail=detail,
            )
            return
        for rid in record_ids:
            if rid not in edge.record_ids:
                edge.record_ids.append(rid)


def _text(record: EvidenceRecord) -> str:
    return f"{record.title} {record.summary or ''}"


def build_graph(records: list[EvidenceRecord]) -> KnowledgeGraph:
    b = _Builder()
    by_category: dict[EvidenceCategory, list[EvidenceRecord]] = {c: [] for c in EvidenceCategory}
    for r in records:
        by_category[r.category].append(r)

    # Diseases and targets (Open Targets)
    for r in by_category[EvidenceCategory.TARGET]:
        md = r.metadata
        symbol = (md.get("target_symbol") or "").upper()
        disease_name = md.get("disease_name")
        if not symbol or not disease_name:
            continue
        disease = b.node(
            f"disease:{normalise_name(disease_name)}",
            "disease",
            disease_name,
            r.record_id,
            data={"ontology_id": md.get("disease_id")},
        )
        target = b.node(
            f"target:{symbol}",
            "target",
            symbol,
            r.record_id,
            url=str(r.source_url),
            data={"name": md.get("target_name"), "ensembl_id": r.identifiers.ensembl_id},
        )
        score = md.get("association_score")
        b.edge(
            target.id,
            disease.id,
            "associated_with",
            [r.record_id],
            f"Open Targets association score {score:.2f}" if isinstance(score, (int, float)) else None,
        )

    # Compounds (ChEMBL) and their mechanism targets; PubChem records attach to their ChEMBL compound
    compound_names: dict[str, str] = {}  # normalised name → compound node id
    chembl_nodes: dict[str, str] = {}
    for r in by_category[EvidenceCategory.COMPOUND]:
        if r.source_name != SourceName.CHEMBL:
            continue
        md = r.metadata
        node = b.node(
            f"compound:{r.source_identifier}",
            "compound",
            r.title,
            r.record_id,
            url=str(r.source_url),
            data={
                "chembl_id": r.source_identifier,
                "max_phase": md.get("max_phase"),
                "max_phase_label": md.get("max_phase_label"),
                "molecule_type": md.get("molecule_type"),
            },
        )
        chembl_nodes[r.source_identifier] = node.id
        for name in [r.title, md.get("query") or "", *(md.get("synonyms") or [])]:
            key = normalise_name(name)
            if len(key) >= MIN_NAME_LENGTH:
                compound_names.setdefault(key, node.id)
        for mech in md.get("mechanisms") or []:
            symbols = [s.upper() for s in mech.get("target_gene_symbols") or []]
            detail = mech.get("mechanism_of_action")
            if symbols:
                for symbol in symbols:
                    target = b.node(
                        f"target:{symbol}", "target", symbol, data={"name": mech.get("target_name")}
                    )
                    b.edge(node.id, target.id, "acts_on", [r.record_id], detail)
            elif mech.get("target_chembl_id"):
                tid = mech["target_chembl_id"]
                target = b.node(
                    f"target:{tid}",
                    "target",
                    mech.get("target_name") or tid,
                    url=f"https://www.ebi.ac.uk/chembl/explore/target/{tid}",
                    data={"chembl_target_id": tid, "target_type": mech.get("target_type")},
                )
                b.edge(node.id, target.id, "acts_on", [r.record_id], detail)
    for r in by_category[EvidenceCategory.COMPOUND]:
        if r.source_name == SourceName.PUBCHEM:
            node_id = chembl_nodes.get(r.metadata.get("linked_chembl_id") or "")
            if node_id:
                node = b.nodes[node_id]
                node.record_ids.append(r.record_id)
                node.data["pubchem_cid"] = r.source_identifier

    # Trials (ClinicalTrials.gov)
    trial_ids: dict[str, str] = {}  # NCT → node id
    for r in by_category[EvidenceCategory.CLINICAL_TRIAL]:
        md = r.metadata
        nct = r.source_identifier
        trial = b.node(
            f"trial:{nct}",
            "trial",
            nct,
            r.record_id,
            url=str(r.source_url),
            data={
                "title": r.title,
                "status": md.get("status_label"),
                "phases": md.get("phases") or [],
                "has_results": md.get("has_results"),
            },
        )
        trial_ids[nct] = trial.id
        for condition in (md.get("conditions") or [])[:MAX_CONDITIONS_PER_TRIAL]:
            key = normalise_name(condition)
            if key:
                disease = b.node(f"disease:{key}", "disease", condition, data={})
                b.edge(trial.id, disease.id, "studies", [r.record_id])
        if md.get("lead_sponsor"):
            sponsor = b.node(f"sponsor:{normalise_name(md['lead_sponsor'])}", "sponsor", md["lead_sponsor"])
            b.edge(trial.id, sponsor.id, "sponsored_by", [r.record_id])
        for item in md.get("interventions") or []:
            name = normalise_name(normalise_intervention_name(item.get("name") or ""))
            compound_id = compound_names.get(name)
            if compound_id:
                compound_records = [
                    rid for rid in b.nodes[compound_id].record_ids if rid.startswith("chembl:")
                ]
                b.edge(trial.id, compound_id, "tests", [r.record_id, *compound_records[:1]], item.get("name"))

    # Publications: explicit NCT numbers and compound names in title/abstract
    name_patterns = [
        (re.compile(rf"\b{re.escape(name)}\b"), node_id)
        for name, node_id in sorted(compound_names.items(), key=lambda kv: -len(kv[0]))
    ]
    for r in by_category[EvidenceCategory.LITERATURE]:
        text = _text(r)
        links: list[tuple[str, Relation, str]] = []
        for nct in dict.fromkeys(_NCT.findall(text)):
            if nct in trial_ids:
                links.append((trial_ids[nct], "references", f"{nct} named in title/abstract"))
        normalised = normalise_name(text)
        seen: set[str] = set()
        for pattern, node_id in name_patterns:
            if node_id not in seen and pattern.search(normalised):
                seen.add(node_id)
                links.append((node_id, "mentions", f"{b.nodes[node_id].label} named in title/abstract"))
        if not links:
            continue
        pub = b.node(
            f"publication:{r.record_id}",
            "publication",
            r.title if len(r.title) <= 90 else r.title[:87] + "…",
            r.record_id,
            url=str(r.source_url),
            data={"date": r.publication_date, "journal": r.journal, "source": r.source_name.value},
        )
        for target_id, relation, detail in links:
            b.edge(pub.id, target_id, relation, [r.record_id], detail)

    nodes = list(b.nodes.values())
    edges = list(b.edges.values())
    unlinked = sum(
        1 for r in by_category[EvidenceCategory.LITERATURE] if f"publication:{r.record_id}" not in b.nodes
    )
    stats = {
        "records": len(records),
        "nodes_by_type": dict(Counter(n.type for n in nodes)),
        "edges_by_relation": dict(Counter(e.relation for e in edges)),
        "publications_without_links": unlinked,
    }
    return KnowledgeGraph(nodes=nodes, edges=edges, stats=stats)
