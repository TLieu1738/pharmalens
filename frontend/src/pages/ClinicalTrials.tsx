import { ArrowUpRight } from 'lucide-react'
import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { EmptyState, FilterBar, Pager, SearchInput, Select } from '@/components/ui/Controls'
import { table } from '@/components/ui/styles'
import { PageHeader } from '@/components/ui/PageHeader'
import { Panel } from '@/components/ui/Panel'
import { StatCard, StatGrid } from '@/components/ui/StatCard'
import { useLibrary } from '@/hooks/useLibrary'
import { trialInfo, trialPhaseRank, type TrialInfo } from '@/lib/evidence'
import { cn, plural } from '@/lib/utils'
import type { LibraryRecord } from '@/types/research'

const PAGE_SIZE = 12
const STOPPED = new Set(['TERMINATED', 'WITHDRAWN', 'SUSPENDED'])
const ACTIVE = new Set(['RECRUITING', 'NOT_YET_RECRUITING', 'ENROLLING_BY_INVITATION', 'ACTIVE_NOT_RECRUITING'])

function statusTone(raw: string): string {
  if (raw === 'RECRUITING' || raw === 'NOT_YET_RECRUITING' || raw === 'ENROLLING_BY_INVITATION') return 'bg-emerald-50 text-emerald-700'
  if (raw === 'ACTIVE_NOT_RECRUITING') return 'bg-accent-50 text-accent-700'
  if (STOPPED.has(raw)) return 'bg-rose-50 text-rose-700'
  return 'bg-slate-100 text-slate-600'
}

const PHASE_SEGMENTS = [
  { rank: 1, label: 'Phase I', cls: 'bg-slate-300' },
  { rank: 2, label: 'Phase II', cls: 'bg-accent-200' },
  { rank: 3, label: 'Phase III', cls: 'bg-accent-600' },
  { rank: 4, label: 'Phase IV', cls: 'bg-ink-900' },
]

export default function ClinicalTrials() {
  const { records, error } = useLibrary()
  const [query, setQuery] = useState('')
  const [phase, setPhase] = useState('all')
  const [status, setStatus] = useState('all')
  const [page, setPage] = useState(1)

  const trials = useMemo(
    () =>
      (records ?? [])
        .filter((r) => r.category === 'clinical_trial')
        .map((r) => ({ record: r, info: trialInfo(r) }))
        .sort((a, b) => (b.info.completionDate ?? '').localeCompare(a.info.completionDate ?? '')),
    [records],
  )
  const statuses = [...new Map(trials.map((t) => [t.info.statusRaw, t.info.status])).entries()].sort((a, b) => a[1].localeCompare(b[1]))

  const filtered = trials.filter(({ record, info }) => {
    const hay = [record.title, info.nctId, info.sponsor, ...info.conditions, ...info.interventions].join(' ').toLowerCase()
    return (
      (!query || query.toLowerCase().split(/\s+/).every((t) => hay.includes(t))) &&
      (phase === 'all' || String(trialPhaseRank(info)) === phase) &&
      (status === 'all' || info.statusRaw === status)
    )
  })
  const pages = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE))
  const current = Math.min(page, pages)

  const phaseCounts = PHASE_SEGMENTS.map((s) => ({ ...s, n: trials.filter((t) => trialPhaseRank(t.info) === s.rank).length }))
  const phased = phaseCounts.reduce((sum, s) => sum + s.n, 0)
  const stopped = trials.filter((t) => STOPPED.has(t.info.statusRaw))

  return (
    <div className="space-y-6">
      <PageHeader
        crumbs={[{ label: 'Workspace', to: '/' }, { label: 'Clinical trials' }]}
        title="Clinical Trials"
        subtitle="The registered-trial landscape across your research, as reported by ClinicalTrials.gov. Registration and status are not evidence that an intervention works."
      />

      <StatGrid>
        <StatCard label="Trials identified" value={records ? trials.length : '—'} hint={records ? plural(new Set(trials.flatMap((t) => t.record.sessions.map((s) => s.session_id))).size, 'session') : undefined} />
        <StatCard
          label="Recruiting or active"
          value={records ? trials.filter((t) => ACTIVE.has(t.info.statusRaw)).length : '—'}
          hint={trials.length ? `${Math.round((trials.filter((t) => ACTIVE.has(t.info.statusRaw)).length / trials.length) * 100)}% of identified trials` : undefined}
        />
        <StatCard label="Phase III or later" value={records ? trials.filter((t) => trialPhaseRank(t.info) >= 3).length : '—'} hint="Late-stage programmes" />
        <StatCard label="Stopped early" value={records ? stopped.length : '—'} hint="Terminated, withdrawn or suspended" />
      </StatGrid>

      <FilterBar>
        <SearchInput
          value={query}
          onChange={(v) => {
            setQuery(v)
            setPage(1)
          }}
          placeholder="Search drug, sponsor, condition or NCT ID…"
          className="min-w-[16rem] flex-[2]"
        />
        <Select
          label="Phase"
          value={phase}
          onChange={(v) => {
            setPhase(v)
            setPage(1)
          }}
          options={[{ value: 'all', label: 'All phases' }, ...PHASE_SEGMENTS.map((s) => ({ value: String(s.rank), label: s.label })), { value: '0', label: 'No phase / N/A' }]}
        />
        <Select
          label="Status"
          value={status}
          onChange={(v) => {
            setStatus(v)
            setPage(1)
          }}
          options={[{ value: 'all', label: 'All statuses' }, ...statuses.map(([raw, label]) => ({ value: raw, label }))]}
        />
      </FilterBar>

      {error ? (
        <p className="text-sm text-rose-700">{error}</p>
      ) : !records ? (
        <p className="text-sm text-slate-500">Loading trials…</p>
      ) : !trials.length ? (
        <EmptyState title="No trials yet">
          Trials retrieved by the Clinical Intelligence agent appear here.{' '}
          <Link to="/" className="font-medium text-accent-700 hover:underline">
            Start research
          </Link>
        </EmptyState>
      ) : filtered.length === 0 ? (
        <EmptyState title="No trials match these filters" />
      ) : (
        <TrialTable rows={filtered.slice((current - 1) * PAGE_SIZE, current * PAGE_SIZE)} total={filtered.length} page={current} pages={pages} onPage={setPage} />
      )}

      {trials.length > 0 && (
        <div className="grid gap-6 lg:grid-cols-2">
          <Panel title="Development phase" subtitle={`${phased} of ${trials.length} trials report a phase`}>
            <div className="flex h-5 overflow-hidden rounded" role="img" aria-label={phaseCounts.map((s) => `${s.label}: ${s.n}`).join(', ')}>
              {phaseCounts.map((s) => (s.n ? <div key={s.rank} className={s.cls} style={{ width: `${(s.n / Math.max(phased, 1)) * 100}%` }} /> : null))}
            </div>
            <div className="mt-3 flex flex-wrap gap-x-6 gap-y-1 text-xs text-slate-600">
              {phaseCounts.map((s) => (
                <span key={s.rank} className="flex items-center gap-1.5">
                  <span className={cn('h-2.5 w-2.5 rounded-sm', s.cls)} aria-hidden="true" />
                  {s.label} · {s.n}
                </span>
              ))}
            </div>
          </Panel>
          <Panel title={`${stopped.length} ${stopped.length === 1 ? 'trial' : 'trials'} stopped early`} className={stopped.length ? 'border-amber-200 bg-amber-50/40' : undefined}>
            {stopped.length === 0 ? (
              <p className="text-sm text-slate-600">None of the identified trials were terminated, withdrawn or suspended.</p>
            ) : (
              <ul className="space-y-2.5">
                {stopped.slice(0, 4).map(({ record, info }) => (
                  <li key={record.record_id} className="text-sm">
                    <a href={record.source_url} target="_blank" rel="noreferrer" className="font-medium text-ink-900 hover:text-accent-700">
                      {info.nctId}
                    </a>{' '}
                    <span className="text-slate-600">· {info.status}</span>
                    <p className="line-clamp-2 text-xs text-slate-600">{info.whyStopped ? `Reason given: ${info.whyStopped}` : 'No reason recorded in the registry.'}</p>
                  </li>
                ))}
              </ul>
            )}
          </Panel>
        </div>
      )}
    </div>
  )
}

function TrialTable({
  rows,
  total,
  page,
  pages,
  onPage,
}: {
  rows: { record: LibraryRecord; info: TrialInfo }[]
  total: number
  page: number
  pages: number
  onPage: (p: number) => void
}) {
  return (
    <div className={table.wrap}>
      <table className={table.table}>
        <thead className={table.head}>
          <tr>
            <th className={table.th}>Study</th>
            <th className={table.th}>Phase</th>
            <th className={table.th}>Status</th>
            <th className={table.th}>Enrolment</th>
            <th className={table.th}>Completion</th>
            <th className={table.th}>
              <span className="sr-only">Open</span>
            </th>
          </tr>
        </thead>
        <tbody>
          {rows.map(({ record, info }) => (
            <tr key={record.record_id} className={table.row}>
              <td className={`${table.td} max-w-md`}>
                <p className="line-clamp-2 font-medium text-ink-900">{record.title}</p>
                <p className="mt-0.5 line-clamp-1 text-xs text-slate-500">
                  {[info.nctId, info.interventions.slice(0, 2).join(', '), info.conditions.slice(0, 2).join(', ')].filter(Boolean).join(' · ')}
                </p>
              </td>
              <td className={`${table.td} whitespace-nowrap text-slate-600`}>{info.phaseLabel}</td>
              <td className={table.td}>
                <span className={cn('inline-block whitespace-nowrap rounded px-2.5 py-1 text-xs', statusTone(info.statusRaw))}>{info.status}</span>
                {!info.hasResults && info.statusRaw === 'COMPLETED' && <p className="mt-1 text-[11px] text-slate-500">No posted results</p>}
              </td>
              <td className={`${table.td} tabular-nums text-slate-600`}>{info.enrollment?.toLocaleString() ?? '—'}</td>
              <td className={`${table.td} whitespace-nowrap text-slate-600`}>{info.completionDate ?? '—'}</td>
              <td className={table.td}>
                <a href={record.source_url} target="_blank" rel="noreferrer" aria-label={`Open ${info.nctId} on ClinicalTrials.gov`}>
                  <ArrowUpRight className="h-4 w-4 text-accent-600" aria-hidden="true" />
                </a>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <div className="flex flex-wrap items-center justify-between gap-3 border-t border-slate-100 px-5 py-3 text-xs text-slate-500">
        <span>
          Showing {rows.length} of {total} trials · Source: ClinicalTrials.gov registry data
        </span>
        <Pager page={page} pages={pages} onChange={onPage} />
      </div>
    </div>
  )
}
