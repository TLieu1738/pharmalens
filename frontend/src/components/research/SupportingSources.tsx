import { ArrowUpRight } from 'lucide-react'
import { useState } from 'react'
import { Link } from 'react-router-dom'
import { Panel } from '@/components/ui/Panel'
import { qualitySummary } from '@/lib/evidence'
import { EVIDENCE_TYPE_LABELS, SOURCE_LABELS } from '@/lib/labels'
import { cn } from '@/lib/utils'
import type { EvidenceRecord, Reference } from '@/types/research'

const TONES = {
  success: 'bg-emerald-50 text-emerald-700',
  warn: 'bg-amber-50 text-amber-800',
  danger: 'bg-rose-50 text-rose-700',
  neutral: 'bg-slate-100 text-slate-600',
}

/** The report's numbered references, with the validation step's quality notes for each record. */
export function SupportingSources({ references, records }: { references: Reference[]; records: EvidenceRecord[] | null }) {
  const [showAll, setShowAll] = useState(false)
  const byId = new Map((records ?? []).map((r) => [r.record_id, r]))
  const shown = showAll ? references : references.slice(0, 6)

  return (
    <Panel title="Supporting sources" subtitle={`${references.length} cited records · numbered as in the report`}>
      <ol className="space-y-5">
        {shown.map((ref) => {
          const record = byId.get(ref.record_id)
          const quality = record ? qualitySummary(record) : null
          return (
            <li key={ref.record_id}>
              <div className="flex gap-2">
                <a href={ref.source_url} target="_blank" rel="noreferrer" className="group min-w-0 flex-1">
                  <p className="text-sm font-medium leading-snug text-ink-900 group-hover:text-accent-700">
                    [{ref.number}] <span className="line-clamp-2 inline">{ref.title}</span>
                  </p>
                </a>
                <a href={ref.source_url} target="_blank" rel="noreferrer" aria-label={`Open reference ${ref.number} at source`}>
                  <ArrowUpRight className="h-4 w-4 shrink-0 text-accent-600" aria-hidden="true" />
                </a>
              </div>
              <p className="mt-1 text-xs text-slate-500">{EVIDENCE_TYPE_LABELS[ref.evidence_type]}</p>
              <p className="mt-0.5 text-xs font-medium text-accent-700">
                {SOURCE_LABELS[ref.source_name]}
                {ref.publication_date ? ` · ${ref.publication_date.slice(0, 4)}` : ''}
              </p>
              {quality && (
                <span title={quality.detail.join(', ') || undefined} className={cn('mt-1.5 inline-block rounded px-2.5 py-1 text-xs', TONES[quality.tone])}>
                  {quality.label}
                </span>
              )}
            </li>
          )
        })}
      </ol>
      <div className="mt-5 flex items-center justify-between text-[13px] font-medium">
        {references.length > 6 ? (
          <button onClick={() => setShowAll((s) => !s)} className="text-accent-700 hover:underline">
            {showAll ? 'Show fewer' : `Show all ${references.length}`}
          </button>
        ) : (
          <span />
        )}
        <Link to="/evidence" className="text-accent-700 hover:underline">
          Open evidence library →
        </Link>
      </div>
    </Panel>
  )
}
