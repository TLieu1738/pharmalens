import { SOURCE_LABELS } from '@/lib/labels'
import type { ResearchPlan } from '@/types/research'

function Row({ label, values }: { label: string; values: string[] }) {
  if (!values.length) return null
  return (
    <div className="grid grid-cols-[8.5rem_1fr] gap-2 py-1.5 text-sm">
      <dt className="text-xs font-medium uppercase tracking-wide text-slate-500">{label}</dt>
      <dd className="flex flex-wrap gap-1.5">
        {values.map((v) => (
          <span key={v} className="rounded bg-slate-100 px-1.5 py-0.5 text-xs text-ink-800">
            {v}
          </span>
        ))}
      </dd>
    </div>
  )
}

export function PlanSummary({ plan }: { plan: ResearchPlan }) {
  return (
    <div>
      {plan.rationale && <p className="mb-3 text-sm leading-relaxed text-slate-700">{plan.rationale}</p>}
      <dl className="divide-y divide-slate-100">
        <Row label="Disease area" values={plan.disease_area ? [plan.disease_area] : []} />
        <Row label="Targets" values={plan.biological_targets} />
        <Row label="Gene symbols" values={plan.target_gene_symbols} />
        <Row label="Compounds" values={plan.compounds} />
        <Row label="Trial terms" values={[plan.clinical_condition ?? '', ...plan.clinical_intervention_terms].filter(Boolean)} />
        <Row label="Sources" values={plan.sources.map((s) => SOURCE_LABELS[s])} />
      </dl>
      <p className="mt-3 rounded bg-slate-50 px-2.5 py-2 font-mono text-[11.5px] text-slate-600">
        <span className="text-slate-400">literature_query: </span>
        {plan.literature_query}
      </p>
    </div>
  )
}
