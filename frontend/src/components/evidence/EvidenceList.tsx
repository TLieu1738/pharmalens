import { useMemo, useState } from 'react'
import { EVIDENCE_TYPE_LABELS } from '@/lib/labels'
import type { EvidenceRecord, EvidenceType } from '@/types/research'
import { EvidenceCard } from './EvidenceCard'

interface Props {
  records: EvidenceRecord[]
  citedNumbers: Map<string, number>
  emptyMessage: string
  note?: string
}

export function EvidenceList({ records, citedNumbers, emptyMessage, note }: Props) {
  const [type, setType] = useState<EvidenceType | 'all'>('all')
  const [citedOnly, setCitedOnly] = useState(false)
  const types = useMemo(() => [...new Set(records.map((r) => r.evidence_type))], [records])
  const shown = records.filter(
    (r) => (type === 'all' || r.evidence_type === type) && (!citedOnly || citedNumbers.has(r.record_id)),
  )

  if (!records.length) {
    return <p className="rounded-lg border border-dashed border-slate-300 bg-white px-4 py-10 text-center text-sm text-slate-500">{emptyMessage}</p>
  }

  return (
    <div className="space-y-3">
      {note && <p className="text-xs leading-relaxed text-slate-500">{note}</p>}
      <div className="flex flex-wrap items-center gap-2 text-xs">
        {types.length > 1 && (
          <select
            value={type}
            onChange={(e) => setType(e.target.value as EvidenceType | 'all')}
            className="rounded-md border border-slate-200 bg-white px-2 py-1 text-xs text-ink-800"
            aria-label="Filter by evidence type"
          >
            <option value="all">All types</option>
            {types.map((t) => (
              <option key={t} value={t}>
                {EVIDENCE_TYPE_LABELS[t]}
              </option>
            ))}
          </select>
        )}
        <label className="inline-flex items-center gap-1.5 text-slate-600">
          <input type="checkbox" checked={citedOnly} onChange={(e) => setCitedOnly(e.target.checked)} className="accent-teal-700" />
          Cited in report only
        </label>
        <span className="ml-auto font-mono text-slate-400">
          {shown.length} of {records.length}
        </span>
      </div>
      {shown.map((r) => (
        <EvidenceCard key={r.record_id} record={r} refNumber={citedNumbers.get(r.record_id)} />
      ))}
    </div>
  )
}
