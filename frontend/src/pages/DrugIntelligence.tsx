import { ArrowUpRight } from 'lucide-react'
import { useMemo, useState } from 'react'
import { Link, Navigate, useNavigate, useParams } from 'react-router-dom'
import { EmptyState, Select } from '@/components/ui/Controls'
import { table } from '@/components/ui/styles'
import { PageHeader } from '@/components/ui/PageHeader'
import { Panel } from '@/components/ui/Panel'
import { Tabs } from '@/components/ui/Tabs'
import { useLibrary } from '@/hooks/useLibrary'
import { compoundInfo, mentions, trialInfo, year, type CompoundInfo } from '@/lib/evidence'
import { EVIDENCE_TYPE_LABELS, SOURCE_LABELS, formatDate } from '@/lib/labels'
import type { LibraryRecord } from '@/types/research'

function names(c: CompoundInfo): string[] {
  return [c.name, ...c.synonyms].filter((n) => n.length >= 4)
}

function Fact({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <dt className="text-[10px] font-semibold uppercase tracking-[0.1em] text-slate-500">{label}</dt>
      <dd className="mt-1 text-sm font-medium text-ink-900">{children}</dd>
    </div>
  )
}

export default function DrugIntelligence() {
  const { chemblId } = useParams()
  const navigate = useNavigate()
  const { records, error } = useLibrary()
  const [tab, setTab] = useState('profile')

  const compounds = useMemo(
    () =>
      (records ?? [])
        .filter((r) => r.category === 'compound')
        .map((r) => ({ record: r, info: compoundInfo(r) }))
        .sort((a, b) => (b.info.maxPhase ?? -1) - (a.info.maxPhase ?? -1) || a.info.name.localeCompare(b.info.name)),
    [records],
  )

  const selected = compounds.find((c) => c.info.chemblId === chemblId)

  const linked = useMemo(() => {
    if (!selected || !records) return { trials: [] as LibraryRecord[], literature: [] as LibraryRecord[] }
    const ns = names(selected.info)
    const hit = (text: string) => ns.some((n) => mentions(text, n))
    return {
      trials: records.filter((r) => r.category === 'clinical_trial' && (hit(r.title) || trialInfo(r).interventions.some(hit))),
      literature: records.filter((r) => r.category === 'literature' && hit(`${r.title} ${r.summary ?? ''}`)),
    }
  }, [selected, records])

  if (error) return <p className="text-sm text-rose-700">{error}</p>
  if (!records) return <p className="text-sm text-slate-500">Loading compounds…</p>
  if (!compounds.length) {
    return (
      <div className="space-y-6">
        <PageHeader crumbs={[{ label: 'Workspace', to: '/' }, { label: 'Drug intelligence' }]} title="Drug Intelligence" />
        <EmptyState title="No compounds yet">
          The Compound agent looks up drugs named in your question and in retrieved trials.{' '}
          <Link to="/" className="font-medium text-accent-700 hover:underline">
            Start research
          </Link>
        </EmptyState>
      </div>
    )
  }
  if (!selected) return <Navigate to={`/drugs/${compounds[0].info.chemblId}`} replace />

  const { info, record } = selected
  const conditionCounts = [...linked.trials.flatMap((t) => trialInfo(t).conditions).reduce((m, c) => m.set(c, (m.get(c) ?? 0) + 1), new Map<string, number>())]
    .sort((a, b) => b[1] - a[1])
    .slice(0, 5)
  const maxCount = Math.max(1, ...conditionCounts.map(([, n]) => n))
  const recent = [
    ...linked.trials.map((r) => ({ r, kind: 'Trial record', date: trialInfo(r).startDate ?? r.publication_date })),
    ...linked.literature.map((r) => ({ r, kind: EVIDENCE_TYPE_LABELS[r.evidence_type], date: r.publication_date })),
  ]
    .sort((a, b) => (b.date ?? '').localeCompare(a.date ?? ''))
    .slice(0, 4)

  return (
    <div className="space-y-6">
      <PageHeader
        crumbs={[{ label: 'Workspace', to: '/' }, { label: 'Drug intelligence', to: '/drugs' }, { label: info.name }]}
        title="Drug Intelligence"
        subtitle="Connect mechanism, development status and the evidence you have retrieved, in one compound profile."
      />

      <section className="rounded-lg border border-slate-200 bg-white px-6 py-5">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <div className="flex flex-wrap items-center gap-3">
              <h2 className="text-2xl font-semibold capitalize tracking-tight text-ink-900">{info.name.toLowerCase()}</h2>
              {info.mechanisms[0] && <span className="rounded bg-slate-100 px-2.5 py-1 text-xs text-slate-700">{info.mechanisms[0].mechanism}</span>}
              {info.withdrawn && <span className="rounded bg-rose-50 px-2.5 py-1 text-xs text-rose-700">Withdrawn</span>}
              {info.blackBoxWarning && <span className="rounded bg-amber-50 px-2.5 py-1 text-xs text-amber-800">Boxed warning</span>}
            </div>
            <a href={record.source_url} target="_blank" rel="noreferrer" className="mt-1 inline-flex items-center gap-1 text-[13px] text-accent-700 hover:underline">
              {info.chemblId} on ChEMBL <ArrowUpRight className="h-3.5 w-3.5" aria-hidden="true" />
            </a>
          </div>
          <div className="w-56">
            <Select
              label="Change compound"
              value={info.chemblId}
              onChange={(id) => navigate(`/drugs/${id}`)}
              options={compounds.map((c) => ({ value: c.info.chemblId, label: c.info.name }))}
            />
          </div>
        </div>
        <dl className="mt-5 grid grid-cols-2 gap-4 border-t border-slate-100 pt-4 md:grid-cols-4">
          <Fact label="Molecule type">{info.moleculeType ?? '—'}</Fact>
          <Fact label="Mechanism">{info.mechanisms.length ? info.mechanisms.map((m) => m.mechanism).join('; ') : 'Not recorded'}</Fact>
          <Fact label="Max development phase">{info.maxPhaseLabel ?? '—'}</Fact>
          <Fact label="First approval">{info.firstApproval ?? 'Not approved / not recorded'}</Fact>
        </dl>
        <p className="mt-4 text-xs text-slate-500">Max phase is the highest phase reached for any indication in ChEMBL, not necessarily for the disease you researched.</p>
      </section>

      <Tabs
        items={[
          { id: 'profile', label: 'Profile' },
          { id: 'trials', label: 'Clinical development', count: linked.trials.length },
          { id: 'literature', label: 'Evidence', count: linked.literature.length },
        ]}
        active={tab}
        onChange={setTab}
      />

      <div role="tabpanel" id={`panel-${tab}`} aria-labelledby={`tab-${tab}`}>
        {tab === 'profile' && (
          <div className="grid gap-6 lg:grid-cols-[minmax(0,1.5fr)_minmax(0,1fr)]">
            <div className="space-y-6">
              <Panel title="Trial landscape" subtitle="Your retrieved trials that name this compound, by condition">
                {conditionCounts.length === 0 ? (
                  <p className="text-sm text-slate-500">No retrieved trials name this compound.</p>
                ) : (
                  <ul className="space-y-3">
                    {conditionCounts.map(([condition, n]) => (
                      <li key={condition} className="grid grid-cols-[10rem_1fr_2rem] items-center gap-3 text-[13px]">
                        <span className="truncate text-slate-600" title={condition}>
                          {condition}
                        </span>
                        <span className="h-2.5 rounded-full bg-slate-100">
                          <span className="block h-2.5 rounded-full bg-accent-600" style={{ width: `${(n / maxCount) * 100}%` }} />
                        </span>
                        <span className="text-right font-medium tabular-nums text-ink-900">{n}</span>
                      </li>
                    ))}
                  </ul>
                )}
                <p className="mt-4 text-xs text-slate-500">Counts reflect only the top-ranked records retrieved in your sessions, not the full registry.</p>
              </Panel>
              <Panel title="Other compounds in your library">
                <ul className="divide-y divide-slate-100">
                  {compounds
                    .filter((c) => c.info.chemblId !== info.chemblId)
                    .slice(0, 6)
                    .map((c) => (
                      <li key={c.info.chemblId} className="grid grid-cols-[1fr_1fr_auto] items-center gap-3 py-2.5 text-sm">
                        <Link to={`/drugs/${c.info.chemblId}`} className="font-medium capitalize text-ink-900 hover:text-accent-700">
                          {c.info.name.toLowerCase()}
                        </Link>
                        <span className="truncate text-slate-500">{c.info.mechanisms[0]?.mechanism ?? c.info.moleculeType ?? '—'}</span>
                        <span className="text-xs text-slate-500">{c.info.maxPhaseLabel ?? ''}</span>
                      </li>
                    ))}
                </ul>
              </Panel>
            </div>
            <Panel title="Recent intelligence" subtitle="Newest linked records from your sessions">
              {recent.length === 0 ? (
                <p className="text-sm text-slate-500">No linked trials or publications yet.</p>
              ) : (
                <ul className="space-y-5">
                  {recent.map(({ r, kind, date }) => (
                    <li key={r.record_id}>
                      <p className="text-[11px] font-medium uppercase tracking-wide text-slate-500">{date ? formatDate(date) : 'Undated'}</p>
                      <p className="mt-1 text-sm font-medium text-ink-900">{kind}</p>
                      <p className="mt-0.5 line-clamp-2 text-[13px] text-slate-600">{r.title}</p>
                      <a href={r.source_url} target="_blank" rel="noreferrer" className="mt-1 inline-flex items-center gap-1 text-xs font-medium text-accent-700 hover:underline">
                        {SOURCE_LABELS[r.source_name]} <ArrowUpRight className="h-3 w-3" aria-hidden="true" />
                      </a>
                    </li>
                  ))}
                </ul>
              )}
            </Panel>
          </div>
        )}

        {tab === 'trials' && <LinkedTable rows={linked.trials} empty="No retrieved trials name this compound." trial />}
        {tab === 'literature' && <LinkedTable rows={linked.literature} empty="No retrieved publications mention this compound." />}
      </div>
    </div>
  )
}

function LinkedTable({ rows, empty, trial = false }: { rows: LibraryRecord[]; empty: string; trial?: boolean }) {
  if (!rows.length) return <EmptyState title={empty} />
  return (
    <div className={table.wrap}>
      <table className={table.table}>
        <thead className={table.head}>
          <tr>
            <th className={table.th}>{trial ? 'Study' : 'Publication'}</th>
            <th className={table.th}>{trial ? 'Status' : 'Type'}</th>
            <th className={table.th}>{trial ? 'Phase' : 'Year'}</th>
            <th className={table.th}>
              <span className="sr-only">Open</span>
            </th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => {
            const t = trial ? trialInfo(r) : null
            return (
              <tr key={r.record_id} className={table.row}>
                <td className={`${table.td} max-w-xl`}>
                  <p className="line-clamp-2 font-medium text-ink-900">{r.title}</p>
                  <p className="mt-0.5 text-xs text-slate-500">{t ? t.nctId : [r.journal, SOURCE_LABELS[r.source_name]].filter(Boolean).join(' · ')}</p>
                </td>
                <td className={`${table.td} whitespace-nowrap text-slate-600`}>{t ? t.status : EVIDENCE_TYPE_LABELS[r.evidence_type]}</td>
                <td className={`${table.td} whitespace-nowrap text-slate-600`}>{t ? t.phaseLabel : (year(r) ?? '—')}</td>
                <td className={table.td}>
                  <a href={r.source_url} target="_blank" rel="noreferrer" aria-label="Open at source">
                    <ArrowUpRight className="h-4 w-4 text-accent-600" aria-hidden="true" />
                  </a>
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}
