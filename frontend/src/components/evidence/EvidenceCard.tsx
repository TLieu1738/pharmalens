import { ExternalLink } from 'lucide-react'
import { useState } from 'react'
import { Badge } from '@/components/ui/Badge'
import { EVIDENCE_TYPE_LABELS, FLAG_LABELS, SERIOUS_FLAGS, SOURCE_LABELS, formatDate } from '@/lib/labels'
import type { EvidenceRecord } from '@/types/research'

function str(v: unknown): string | null {
  return typeof v === 'string' && v ? v : typeof v === 'number' ? String(v) : null
}

function TrialFacts({ md }: { md: Record<string, unknown> }) {
  const phases = Array.isArray(md.phases) ? (md.phases as string[]).join(', ') : null
  const interventions = Array.isArray(md.interventions)
    ? (md.interventions as { name: string }[]).map((i) => i.name).slice(0, 4).join(', ')
    : null
  const facts = [
    ['Status', str(md.status_label)],
    ['Phase', phases],
    ['Design', [str(md.study_type), str(md.allocation)].filter(Boolean).join(' · ') || null],
    ['Enrolment', str(md.enrollment)],
    ['Sponsor', str(md.lead_sponsor)],
    ['Interventions', interventions],
    ['Results posted', md.has_results ? 'Yes' : 'No'],
  ].filter(([, v]) => v) as [string, string][]
  return <Facts facts={facts} />
}

function CompoundFacts({ md }: { md: Record<string, unknown> }) {
  if (md.linked_chembl_id) {
    // PubChem record: chemical identifiers only (development status comes from ChEMBL)
    const facts = [
      ['Molecular formula', str(md.molecular_formula)],
      ['Molecular weight (g/mol)', str(md.molecular_weight)],
      ['InChIKey', str(md.inchi_key)],
      ['Linked ChEMBL record', str(md.linked_chembl_id)],
    ].filter(([, v]) => v) as [string, string][]
    return <Facts facts={facts} />
  }
  const mechs = Array.isArray(md.mechanisms)
    ? (md.mechanisms as { mechanism_of_action: string }[]).map((m) => m.mechanism_of_action).join('; ')
    : null
  const facts = [
    ['Type', str(md.molecule_type)],
    ['Max phase (any indication)', str(md.max_phase_label)],
    ['First approval', str(md.first_approval)],
    ['Mechanism', mechs || null],
  ].filter(([, v]) => v) as [string, string][]
  return <Facts facts={facts} />
}

function TargetFacts({ md }: { md: Record<string, unknown> }) {
  const facts = [
    ['Association rank', str(md.association_rank)],
    ['Overall association score', str(md.association_score)],
    ['Disease', str(md.disease_name)],
  ].filter(([, v]) => v) as [string, string][]
  return <Facts facts={facts} />
}

function Facts({ facts }: { facts: [string, string][] }) {
  if (!facts.length) return null
  return (
    <dl className="mt-2 grid grid-cols-1 gap-x-4 gap-y-1 text-xs sm:grid-cols-2">
      {facts.map(([k, v]) => (
        <div key={k} className="flex gap-1.5">
          <dt className="shrink-0 text-slate-500">{k}:</dt>
          <dd className="text-ink-800">{v}</dd>
        </div>
      ))}
    </dl>
  )
}

export function EvidenceCard({ record, refNumber }: { record: EvidenceRecord; refNumber?: number }) {
  const [expanded, setExpanded] = useState(false)
  const md = record.metadata
  const authors = record.authors.length
    ? record.authors.slice(0, 3).join(', ') + (record.authors.length > 3 ? ' et al.' : '')
    : null
  const long = (record.summary?.length ?? 0) > 360

  return (
    <article className="rounded-lg border border-slate-200 bg-white p-4" id={`evidence-${record.record_id}`}>
      <div className="flex flex-wrap items-center gap-1.5">
        {refNumber != null && <Badge tone="navy">Cited [{refNumber}]</Badge>}
        <Badge tone="accent">{SOURCE_LABELS[record.source_name]}</Badge>
        <Badge>{EVIDENCE_TYPE_LABELS[record.evidence_type]}</Badge>
        {record.also_found_in.map((s) => (
          <Badge key={s} tone="neutral">
            also in {SOURCE_LABELS[s]}
          </Badge>
        ))}
        {record.quality_flags.map((f) => (
          <Badge key={f} tone={SERIOUS_FLAGS.has(f) ? 'warn' : 'neutral'}>
            {FLAG_LABELS[f] ?? f}
          </Badge>
        ))}
        <span className="ml-auto font-mono text-[11px] text-slate-400">{record.publication_date ?? 'undated'}</span>
      </div>

      <h3 className="mt-2 text-[14.5px] font-medium leading-snug text-ink-900">
        <a href={record.source_url} target="_blank" rel="noreferrer" className="hover:text-accent-700 hover:underline">
          {record.title}
          <ExternalLink className="ml-1 inline h-3 w-3 align-baseline text-slate-400" aria-hidden="true" />
        </a>
      </h3>
      {(authors || record.journal) && (
        <p className="mt-0.5 text-xs text-slate-500">{[authors, record.journal].filter(Boolean).join(' · ')}</p>
      )}

      {record.category === 'clinical_trial' && <TrialFacts md={md} />}
      {record.category === 'compound' && <CompoundFacts md={md} />}
      {record.category === 'target' && <TargetFacts md={md} />}

      {record.summary && (
        <div className="mt-2">
          <p className={`text-[13px] leading-relaxed text-slate-700 ${expanded ? '' : 'line-clamp-3'}`}>{record.summary}</p>
          {long && (
            <button onClick={() => setExpanded((v) => !v)} className="mt-1 text-xs font-medium text-accent-700 hover:underline">
              {expanded ? 'Show less' : 'Show full abstract'}
            </button>
          )}
        </div>
      )}

      <p className="mt-2 font-mono text-[10.5px] text-slate-400">
        {record.source_identifier}
        {record.identifiers.doi && ` · doi:${record.identifiers.doi}`} · retrieved {formatDate(record.retrieved_at, true)}
      </p>
    </article>
  )
}
