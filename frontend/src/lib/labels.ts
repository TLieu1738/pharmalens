import type { AgentName, EvidenceType, SessionStatus, SourceName } from '@/types/research'

export const SOURCE_LABELS: Record<SourceName, string> = {
  pubmed: 'PubMed',
  europe_pmc: 'Europe PMC',
  clinicaltrials_gov: 'ClinicalTrials.gov',
  chembl: 'ChEMBL',
  open_targets: 'Open Targets',
}

export const AGENT_LABELS: Record<AgentName, { name: string; detail: string }> = {
  research_planner: { name: 'Research Planner', detail: 'AI model interprets the question into a search plan' },
  literature_agent: { name: 'Literature Agent', detail: 'PubMed + Europe PMC' },
  clinical_agent: { name: 'Clinical Intelligence Agent', detail: 'ClinicalTrials.gov' },
  target_agent: { name: 'Biological Target Agent', detail: 'Open Targets Platform' },
  compound_agent: { name: 'Compound Agent', detail: 'ChEMBL (plan + trial interventions)' },
  evidence_validation: { name: 'Evidence Validation', detail: 'Deduplication and quality flags' },
  research_synthesis: { name: 'Research Synthesis', detail: 'AI model drafts cited claims' },
  claim_verification: { name: 'Claim Verification', detail: 'Checks citations, numbers and support before publishing' },
}

export const EVIDENCE_TYPE_LABELS: Record<EvidenceType, string> = {
  primary_research: 'Primary research',
  review: 'Review',
  preprint: 'Preprint',
  clinical_trial: 'Clinical trial',
  regulatory: 'Regulatory',
  database_record: 'Database record',
  unknown: 'Unclassified',
}

export const STATUS_LABELS: Record<SessionStatus, string> = {
  pending: 'Queued for planning',
  planning: 'Drafting protocol',
  awaiting_approval: 'Awaiting your approval',
  queued: 'Queued',
  researching: 'Retrieving evidence',
  validating: 'Validating evidence',
  synthesising: 'Writing report',
  completed: 'Completed',
  failed: 'Failed',
  cancelled: 'Cancelled',
}

export const FLAG_LABELS: Record<string, string> = {
  missing_abstract: 'No abstract',
  missing_date: 'No date',
  missing_authors: 'No authors',
  abstract_only: 'Abstract only',
  not_peer_reviewed: 'Not peer reviewed',
  retracted: 'Retracted',
  trial_stopped_early: 'Stopped early',
  trial_no_posted_results: 'No posted results',
  trial_status_unknown: 'Status unknown',
  compound_withdrawn: 'Withdrawn',
}

/** Flags worth drawing attention to (others are informational). */
export const SERIOUS_FLAGS = new Set(['retracted', 'not_peer_reviewed', 'trial_stopped_early', 'compound_withdrawn'])

export function formatDate(iso: string | null | undefined, withTime = false): string {
  if (!iso) return '—'
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return iso
  return d.toLocaleString('en-GB', {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
    ...(withTime ? { hour: '2-digit', minute: '2-digit' } : {}),
  })
}

export function formatDuration(ms: number | null): string {
  if (ms == null) return ''
  return ms < 1000 ? `${ms} ms` : `${(ms / 1000).toFixed(1)} s`
}
