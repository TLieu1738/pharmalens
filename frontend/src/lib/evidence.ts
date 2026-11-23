// Helpers for reading source-specific fields from evidence records. Values come from the source APIs only.
import type { EvidenceRecord } from '@/types/research'
import { FLAG_LABELS, SERIOUS_FLAGS } from './labels'

export function year(record: EvidenceRecord): number | null {
  const y = Number.parseInt(record.publication_date?.slice(0, 4) ?? '', 10)
  return Number.isFinite(y) ? y : null
}

function str(value: unknown): string | null {
  return typeof value === 'string' && value.trim() ? value : null
}

function strList(value: unknown): string[] {
  return Array.isArray(value) ? value.filter((v): v is string => typeof v === 'string' && v.trim() !== '') : []
}

export interface TrialInfo {
  nctId: string
  status: string
  statusRaw: string
  phases: string[]
  phaseLabel: string
  conditions: string[]
  interventions: string[]
  sponsor: string | null
  enrollment: number | null
  startDate: string | null
  completionDate: string | null
  hasResults: boolean
  whyStopped: string | null
}

export function trialInfo(r: EvidenceRecord): TrialInfo {
  const m = r.metadata
  const phases = strList(m.phases)
  const interventions = Array.isArray(m.interventions)
    ? (m.interventions as { name?: unknown }[]).map((i) => str(i?.name)).filter((n): n is string => n !== null)
    : []
  return {
    nctId: r.identifiers.nct_id ?? r.source_identifier,
    status: str(m.status_label) ?? 'Unknown',
    statusRaw: str(m.overall_status) ?? 'UNKNOWN',
    phases,
    phaseLabel: phases.length ? phases.map((p) => p.replace('Phase ', '')).join('/') : '—',
    conditions: strList(m.conditions),
    interventions,
    sponsor: str(m.lead_sponsor),
    enrollment: typeof m.enrollment === 'number' ? m.enrollment : null,
    startDate: str(m.start_date),
    completionDate: str(m.completion_date),
    hasResults: m.has_results === true,
    whyStopped: str(m.why_stopped),
  }
}

/** Highest phase number in a trial (0 if none / early phase 1 counts as 1). */
export function trialPhaseRank(info: TrialInfo): number {
  return Math.max(0, ...info.phases.map((p) => Number.parseInt(p.replace(/\D/g, ''), 10) || 0))
}

export interface CompoundInfo {
  chemblId: string
  name: string
  moleculeType: string | null
  maxPhase: number | null
  maxPhaseLabel: string | null
  firstApproval: number | null
  withdrawn: boolean
  blackBoxWarning: boolean
  synonyms: string[]
  mechanisms: { mechanism: string; actionType: string | null }[]
}

export function compoundInfo(r: EvidenceRecord): CompoundInfo {
  const m = r.metadata
  const mechanisms = Array.isArray(m.mechanisms)
    ? (m.mechanisms as { mechanism_of_action?: unknown; action_type?: unknown }[])
        .map((x) => ({ mechanism: str(x?.mechanism_of_action) ?? '', actionType: str(x?.action_type) }))
        .filter((x) => x.mechanism)
    : []
  return {
    chemblId: r.identifiers.chembl_id ?? r.source_identifier,
    name: r.title,
    moleculeType: str(m.molecule_type),
    maxPhase: typeof m.max_phase === 'number' ? m.max_phase : null,
    maxPhaseLabel: str(m.max_phase_label),
    firstApproval: typeof m.first_approval === 'number' ? m.first_approval : null,
    withdrawn: m.withdrawn === true,
    blackBoxWarning: m.black_box_warning === true,
    synonyms: strList(m.synonyms),
    mechanisms,
  }
}

export interface QualitySummary {
  label: string
  tone: 'success' | 'warn' | 'danger' | 'neutral'
  detail: string[]
}

/**
 * A plain description of what the validation step flagged for a record. This is not a confidence score:
 * it only reports detectable issues (missing metadata, not peer reviewed, stopped early, ...).
 */
export function qualitySummary(r: EvidenceRecord): QualitySummary {
  const detail = r.quality_flags.map((f) => FLAG_LABELS[f] ?? f)
  if (r.quality_flags.some((f) => SERIOUS_FLAGS.has(f))) return { label: detail[0] ?? 'Review', tone: 'danger', detail }
  if (detail.length) return { label: detail.length === 1 ? detail[0] : `${detail.length} notes`, tone: 'warn', detail }
  return { label: 'No issues flagged', tone: 'success', detail }
}

export function mentions(text: string, name: string): boolean {
  return text.toLowerCase().includes(name.toLowerCase())
}
