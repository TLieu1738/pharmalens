// Mirrors backend Pydantic models (app/models/*). Keep in sync.

export type SessionStatus =
  | 'pending'
  | 'planning'
  | 'researching'
  | 'validating'
  | 'synthesising'
  | 'completed'
  | 'failed'

export type AgentName =
  | 'research_planner'
  | 'literature_agent'
  | 'clinical_agent'
  | 'target_agent'
  | 'compound_agent'
  | 'evidence_validation'
  | 'research_synthesis'

export type ExecutionStatus = 'pending' | 'running' | 'completed' | 'partial' | 'failed' | 'skipped'

export type SourceName = 'pubmed' | 'europe_pmc' | 'clinicaltrials_gov' | 'chembl' | 'open_targets'
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
}

export type StatementKind = 'finding' | 'hypothesis' | 'gap'

export interface Statement {
  text: string
  kind: StatementKind
  citations: string[]
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

export interface ReportIntegrity {
  statements_total: number
  statements_removed_unsupported: number
  citations_removed_invalid: number
  findings_with_citations: number
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
}

export interface SessionSummary {
  session_id: string
  research_question: string
  status: SessionStatus
  demo_mode: boolean
  created_at: string
  completed_at: string | null
}

export interface Identifiers {
  doi: string | null
  pmid: string | null
  pmcid: string | null
  nct_id: string | null
  chembl_id: string | null
  ensembl_id: string | null
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

export const TERMINAL_STATUSES: SessionStatus[] = ['completed', 'failed']

export interface SessionRef {
  session_id: string
  research_question: string
  created_at: string
}

/** An evidence record across the user's sessions (deduplicated), with the sessions it was retrieved in. */
export interface LibraryRecord extends EvidenceRecord {
  sessions: SessionRef[]
}
