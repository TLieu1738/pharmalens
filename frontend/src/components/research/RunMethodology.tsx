// Report sections built deterministically from the session record (never written by the AI model).
import type { ReactNode } from 'react'
import { SOURCE_LABELS, formatDate } from '@/lib/labels'
import { retrievalOutcomes } from '@/lib/evidence'
import type { ResearchPlan, SessionDetail, SourceName } from '@/types/research'

function Rows({ label, values }: { label: string; values: (string | null | undefined)[] }) {
  const v = values.filter((x): x is string => Boolean(x && x.trim()))
  if (!v.length) return null
  return (
    <div className="grid gap-1 py-2 sm:grid-cols-[11rem_1fr]">
      <dt className="text-xs font-medium uppercase tracking-wide text-slate-500">{label}</dt>
      <dd className="text-sm text-ink-900">
        {v.length === 1 ? (
          v[0]
        ) : (
          <ul className="list-disc space-y-0.5 pl-4">
            {v.map((x) => (
              <li key={x}>{x}</li>
            ))}
          </ul>
        )}
      </dd>
    </div>
  )
}

function years(plan: ResearchPlan): string | null {
  if (!plan.date_from && !plan.date_to) return null
  return `${plan.date_from ?? 'any'} to ${plan.date_to ?? 'present'}`
}

/** The protocol as approved by the user. */
export function ProtocolSummary({ plan, approvedAt }: { plan: ResearchPlan; approvedAt: string | null }) {
  return (
    <div>
      <p className="text-xs text-slate-500">{approvedAt ? `Approved ${formatDate(approvedAt, true)}` : 'Run with the drafted protocol (no approval step recorded).'}</p>
      <dl className="mt-1 divide-y divide-slate-100">
        <Rows label="Objective" values={[plan.objective]} />
        <Rows label="Key questions" values={plan.key_questions ?? []} />
        <Rows label="Disease / condition" values={[plan.disease_area]} />
        <Rows label="Targets" values={[(plan.biological_targets ?? []).join(', ')]} />
        <Rows label="Compounds" values={[(plan.compounds ?? []).join(', ')]} />
        <Rows label="Drug classes (trials)" values={[(plan.clinical_intervention_terms ?? []).join(', ')]} />
        <Rows label="Inclusion criteria" values={plan.inclusion_criteria ?? []} />
        <Rows label="Exclusion criteria" values={plan.exclusion_criteria ?? []} />
        <Rows label="Intended outputs" values={plan.intended_outputs ?? []} />
        <Rows label="Known limitations" values={plan.known_limitations ?? []} />
      </dl>
    </div>
  )
}

/** A plain-language methodology paragraph, generated from what actually ran. */
export function Methodology({ session }: { session: SessionDetail }) {
  const plan = session.research_plan
  if (!plan) return null
  const outcomes = retrievalOutcomes(session)
  const queried = [...new Set(outcomes.map((o) => SOURCE_LABELS[o.source as SourceName] ?? o.source))]
  const failed = [...new Set(outcomes.filter((o) => !o.ok).map((o) => SOURCE_LABELS[o.source as SourceName] ?? o.source))]
  const dedup = session.run_audit?.deduplication
  const integrity = session.report?.integrity
  const queries = [plan.literature_query, ...(plan.additional_literature_queries ?? [])]
  const parts: ReactNode[] = [
    `${queried.length} public ${queried.length === 1 ? 'source was' : 'sources were'} queried live (${queried.join(', ') || 'none'}). `,
    `Literature was searched with ${queries.length} ${queries.length === 1 ? 'query' : 'queries'}, taking up to ${plan.max_results_per_source ?? 20} top-ranked records per source`,
    years(plan) ? `, limited to ${years(plan)}` : '',
    plan.include_preprints === false ? ', excluding preprints' : '',
    '. ',
    dedup ? `${dedup.records_retrieved} records were retrieved; ${dedup.duplicates_merged} cross-source duplicates were merged by stable identifiers, leaving ${dedup.unique_records} unique records. ` : '',
    'A rule-based validation step flagged missing metadata, preprints, stopped trials and withdrawn compounds. ',
    integrity?.records_provided != null ? `The synthesis model read ${integrity.records_provided} of ${integrity.records_available} validated records` : 'The synthesis model read the validated records',
    ' and every finding was then checked against them in code',
    integrity ? `: ${integrity.statements_removed_unsupported} unsupported ${integrity.statements_removed_unsupported === 1 ? 'statement was' : 'statements were'} removed and ${integrity.citations_removed_invalid} invalid ${integrity.citations_removed_invalid === 1 ? 'citation' : 'citations'} dropped. ` : '. ',
    failed.length ? `Unavailable during this run: ${failed.join(', ')}. ` : '',
    'This is a rapid evidence briefing from top-ranked records, not a systematic review.',
  ]
  return <p className="text-[14px] leading-relaxed text-slate-700">{parts}</p>
}

/** Per-source, per-query coverage: what matched at the source versus what was retrieved. */
export function DataSourcesTable({ session }: { session: SessionDetail }) {
  const outcomes = retrievalOutcomes(session)
  if (!outcomes.length) return <p className="text-sm text-slate-500">No retrieval was recorded.</p>
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-left text-[13px]">
        <thead className="border-b border-slate-200 text-[11px] font-semibold uppercase tracking-wide text-slate-500">
          <tr>
            <th className="py-2 pr-3">Source</th>
            <th className="py-2 pr-3">Query</th>
            <th className="py-2 pr-3 text-right">Matching at source</th>
            <th className="py-2 pr-3 text-right">Retrieved</th>
            <th className="py-2 text-right">Status</th>
          </tr>
        </thead>
        <tbody>
          {outcomes.map((o, i) => (
            <tr key={`${o.source}-${i}`} className="border-b border-slate-100 align-top last:border-0">
              <td className="whitespace-nowrap py-2 pr-3 font-medium text-ink-900">{SOURCE_LABELS[o.source as SourceName] ?? o.source}</td>
              <td className="max-w-md py-2 pr-3 font-mono text-[12px] text-slate-600">{o.query ?? '—'}</td>
              <td className="py-2 pr-3 text-right tabular-nums text-slate-600">{o.total_available != null ? o.total_available.toLocaleString() : 'not reported'}</td>
              <td className="py-2 pr-3 text-right tabular-nums text-ink-900">
                {o.ok ? o.record_count : '—'}
                {o.requested ? <span className="text-slate-400"> / {o.requested}</span> : null}
              </td>
              <td className="py-2 text-right">{o.ok ? <span className="text-emerald-700">OK</span> : <span className="text-rose-700" title={o.error ?? undefined}>Failed</span>}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="mt-2 text-xs text-slate-500">Retrieved / cap set in the protocol. "Matching at source" is the count the database reported for the query.</p>
    </div>
  )
}
