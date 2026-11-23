// Mirrors backend Pydantic models (app/models/*). Keep in sync.

export type SessionStatus =
  | 'pending'
  | 'planning'
  | 'awaiting_approval'
  | 'queued'
  | 'researching'
  | 'validating'
  | 'synthesising'
  | 'completed'
  | 'failed'
  | 'cancelled'

export type AgentName =
  | 'research_planner'
  | 'literature_agent'
  | 'clinical_agent'
  | 'target_agent'
  | 'compound_agent'
  | 'evidence_validation'
  | 'research_synthesis'
  | 'claim_verification'

export type ExecutionStatus = 'pending' | 'running' | 'completed' | 'partial' | 'failed' | 'skipped'

export type SourceName = 'pubmed' | 'europe_pmc' | 'clinicaltrials_gov' | 'chembl' | 'open_targets' | 'pubchem' | 'openalex'
export type EvidenceCategory = 'literature' | 'clinical_trial' | 'compound' | 'target'
export type EvidenceType =
  | 'primary_research'
  | 'review'
  | 'preprint'
  | 'clinical_trial'
  | 'regulatory'
  | 'database_record'
  | 'unknown'

export interface SourceOutcome {
  source: string
  ok: boolean
  record_count: number
  error: string | null
  query?: string | null
  total_available?: number | null
  requested?: number | null
  pages?: number | null
}

export interface AgentExecution {
  agent_name: AgentName
  status: ExecutionStatus
  started_at: string | null
  completed_at: string | null
  duration_ms: number | null
  record_count: number | null
  message: string | null
  error_message: string | null
  sources: SourceOutcome[]
}

export interface ResearchPlan {
  disease_area: string | null
  biological_targets: string[]
  target_gene_symbols: string[]
  compounds: string[]
  concepts: string[]
  objectives: string[]
  literature_query: string
  clinical_condition: string | null
  clinical_intervention_terms: string[]
  sources: SourceName[]
  rationale: string
  // Protocol fields (reviewed and approved by the user before retrieval runs)
  objective: string
  key_questions: string[]
  additional_literature_queries: string[]
  inclusion_criteria: string[]
  exclusion_criteria: string[]
  date_from: number | null
  date_to: number | null
  include_preprints: boolean
  max_results_per_source: number
  intended_outputs: string[]
  known_limitations: string[]
}

export type StatementKind = 'finding' | 'clinical_outcome' | 'comparative_analysis' | 'interpretation' | 'hypothesis' | 'gap'
export type ValidationStatus = 'supported' | 'partially_supported' | 'not_verified' | 'not_applicable' | 'unsupported' | 'contradicted'

export interface Statement {
  text: string
  kind: StatementKind
  citations: string[]
  limitations?: string[]
  validation_status?: ValidationStatus
  validation_notes?: string[]
  support?: { record_id: string; verdict: string }[]
}

export interface ReportSection {
  key: string
  title: string
  statements: Statement[]
}

export interface Reference {
  number: number
  record_id: string
  title: string
  source_name: SourceName
  evidence_type: EvidenceType
  source_url: string
  publication_date: string | null
  retrieved_at: string
}

export interface RemovedStatement {
  section: string
  text: string
  reason: string
  kind?: string | null
  status?: string
  citations?: string[]
}

export interface ReportIntegrity {
  statements_total: number
  statements_removed_unsupported: number
  citations_removed_invalid: number
  findings_with_citations: number
  removed_statements?: RemovedStatement[]
  invalid_citations?: string[]
  records_provided?: number | null
  records_available?: number | null
  validated?: boolean
  semantic_check?: 'completed' | 'unavailable' | 'not_run'
  status_counts?: Record<string, number>
  relabelled?: RemovedStatement[]
}

export interface RunAudit {
  model: { id: string; planner_effort: string; synthesis_effort: string }
  attempts: number
  execution_started_at: string
  execution_finished_at: string
  limits: {
    max_results_per_source: number
    literature_queries: string[]
    date_from: number | null
    date_to: number | null
    include_preprints: boolean
  }
  deduplication: {
    records_retrieved: number
    unique_records: number
    duplicates_merged: number
    merges: { kept: string; merged: string[] }[]
  }
  errors: string[]
}

export interface ResearchReport {
  research_question: string
  scope: string
  sections: ReportSection[]
  references: Reference[]
  integrity: ReportIntegrity
  disclaimer: string
  model: string
  generated_at: string
}

export interface EvidenceProfile {
  total_records: number
  duplicates_removed: number
  by_evidence_type: Record<string, number>
  by_category: Record<string, number>
  by_source: Record<string, number>
  quality_flags: Record<string, number>
  trial_status: Record<string, number>
  publication_year_range: [number, number] | null
  cross_source_matches: number
}

export interface SessionDetail {
  session_id: string
  research_question: string
  status: SessionStatus
  demo_mode: boolean
  created_at: string
  completed_at: string | null
  research_plan: ResearchPlan | null
  agents: AgentExecution[]
  evidence_profile: EvidenceProfile | null
  warnings: string[]
  error_message: string | null
  report: ResearchReport | null
  is_owner: boolean
  protocol_approved_at: string | null
  attempts: number
  run_audit: RunAudit | null
}

export interface SessionSummary {
  session_id: string
  research_question: string
  status: SessionStatus
  demo_mode: boolean
  created_at: string
  completed_at: string | null
  attempts?: number
}

export interface Identifiers {
  doi: string | null
  pmid: string | null
  pmcid: string | null
  nct_id: string | null
  chembl_id: string | null
  ensembl_id: string | null
  openalex_id?: string | null
  pubchem_cid?: string | null
}

export interface EvidenceRecord {
  record_id: string
  source_name: SourceName
  source_identifier: string
  category: EvidenceCategory
  evidence_type: EvidenceType
  title: string
  summary: string | null
  source_url: string
  publication_date: string | null
  retrieved_at: string
  identifiers: Identifiers
  authors: string[]
  journal: string | null
  publication_types: string[]
  // Source-specific fields (trial status, ChEMBL phase, Open Targets score, ...)
  metadata: Record<string, unknown>
  quality_flags: string[]
  also_found_in: SourceName[]
}

export const TERMINAL_STATUSES: SessionStatus[] = ['completed', 'failed', 'cancelled']
/** Statuses where nothing changes until the user acts, so polling can pause. */
export const IDLE_STATUSES: SessionStatus[] = [...TERMINAL_STATUSES, 'awaiting_approval']

export interface SessionRef {
  session_id: string
  research_question: string
  created_at: string
}

/** An evidence record across the user's sessions (deduplicated), with the sessions it was retrieved in. */
export interface LibraryRecord extends EvidenceRecord {
  sessions: SessionRef[]
}

// Knowledge graph (GET /api/graph). Every edge carries the IDs of the records that state it.
export type GraphNodeType = 'disease' | 'target' | 'compound' | 'trial' | 'publication' | 'sponsor'
export type GraphRelation = 'associated_with' | 'acts_on' | 'tests' | 'studies' | 'sponsored_by' | 'references' | 'mentions'

export interface GraphNode {
  id: string
  type: GraphNodeType
  label: string
  record_ids: string[]
  url: string | null
  data: Record<string, unknown>
}

export interface GraphEdge {
  id: string
  source: string
  target: string
  relation: GraphRelation
  record_ids: string[]
  detail: string | null
}

export interface KnowledgeGraph {
  nodes: GraphNode[]
  edges: GraphEdge[]
  stats: {
    records: number
    nodes_by_type: Partial<Record<GraphNodeType, number>>
    edges_by_relation: Partial<Record<GraphRelation, number>>
    publications_without_links: number
  }
}
