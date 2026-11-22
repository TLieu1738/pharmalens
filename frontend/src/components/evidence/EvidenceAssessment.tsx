import { Panel } from '@/components/ui/Panel'
import { EVIDENCE_TYPE_LABELS, FLAG_LABELS, SOURCE_LABELS } from '@/lib/labels'
import type { EvidenceProfile, EvidenceType, ReportIntegrity, SourceName } from '@/types/research'

/** Labelled single-hue bar list: each row names its category and shows the exact count. */
function BarList({ data, label }: { data: [string, number][]; label: string }) {
  const max = Math.max(1, ...data.map(([, v]) => v))
  if (!data.length) return <p className="text-sm text-slate-500">No data.</p>
  return (
    <table className="w-full text-sm" aria-label={label}>
      <tbody>
        {data.map(([name, value]) => (
          <tr key={name} className="group" title={`${name}: ${value}`}>
            <th scope="row" className="w-40 py-1 pr-3 text-left text-xs font-normal text-slate-600">
              {name}
            </th>
            <td className="py-1">
              <div className="flex items-center gap-2">
                <div className="h-2.5 flex-1 rounded-sm bg-slate-100">
                  <div
                    className="h-2.5 rounded-r-[4px] bg-accent-600 transition-opacity group-hover:opacity-80"
                    style={{ width: `${(value / max) * 100}%` }}
                  />
                </div>
                <span className="w-8 text-right font-mono text-xs text-ink-900">{value}</span>
              </div>
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}

const sorted = (o: Record<string, number>) => Object.entries(o).sort((a, b) => b[1] - a[1])

export function EvidenceAssessment({
  profile,
  integrity,
  warnings,
}: {
  profile: EvidenceProfile
  integrity: ReportIntegrity | null
  warnings: string[]
}) {
  const stats = [
    ['Unique records', profile.total_records],
    ['Duplicates merged', profile.duplicates_removed],
    ['Found in 2+ sources', profile.cross_source_matches],
    ['Year range', profile.publication_year_range ? profile.publication_year_range.join('–') : '—'],
  ] as const

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        {stats.map(([k, v]) => (
          <div key={k} className="rounded-lg border border-slate-200 bg-white px-4 py-3">
            <p className="text-xs text-slate-500">{k}</p>
            <p className="mt-1 font-mono text-xl font-semibold text-ink-900">{v}</p>
          </div>
        ))}
      </div>

      {warnings.length > 0 && (
        <Panel title="Evidence caveats">
          <ul className="list-disc space-y-1 pl-5 text-sm text-slate-700">
            {warnings.map((w) => (
              <li key={w}>{w}</li>
            ))}
          </ul>
        </Panel>
      )}

      <div className="grid gap-4 lg:grid-cols-2">
        <Panel title="Records by evidence type">
          <BarList
            label="Records by evidence type"
            data={sorted(profile.by_evidence_type).map(([k, v]) => [EVIDENCE_TYPE_LABELS[k as EvidenceType] ?? k, v])}
          />
        </Panel>
        <Panel title="Records by source (after deduplication)">
          <BarList
            label="Records by source"
            data={sorted(profile.by_source).map(([k, v]) => [SOURCE_LABELS[k as SourceName] ?? k, v])}
          />
        </Panel>
        {Object.keys(profile.trial_status).length > 0 && (
          <Panel title="Clinical trials by registered status">
            <BarList label="Trials by status" data={sorted(profile.trial_status)} />
            <p className="mt-3 text-xs text-slate-500">Registration status describes study progress, not whether an intervention works.</p>
          </Panel>
        )}
        <Panel title="Data-quality flags">
          <BarList label="Quality flags" data={sorted(profile.quality_flags).map(([k, v]) => [FLAG_LABELS[k] ?? k, v])} />
          <p className="mt-3 text-xs text-slate-500">Flags are rule-based metadata checks, not judgements of scientific merit.</p>
        </Panel>
      </div>

      {integrity && (
        <Panel title="Report grounding check">
          <ul className="space-y-1 text-sm text-slate-700">
            <li>
              <span className="font-mono">{integrity.findings_with_citations}</span> findings, each linked to at least one retrieved record.
            </li>
            <li>
              <span className="font-mono">{integrity.statements_removed_unsupported}</span> statements removed because they cited no valid evidence.
            </li>
            <li>
              <span className="font-mono">{integrity.citations_removed_invalid}</span> citations removed because they did not match a retrieved record.
            </li>
          </ul>
        </Panel>
      )}
    </div>
  )
}
