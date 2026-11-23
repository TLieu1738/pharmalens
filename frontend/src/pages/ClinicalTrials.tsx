import { ArrowUpRight, X } from 'lucide-react'
import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { EmptyState, FilterBar, Pager, SearchInput, Select } from '@/components/ui/Controls'
import { table } from '@/components/ui/styles'
import { PageHeader } from '@/components/ui/PageHeader'
import { Panel } from '@/components/ui/Panel'
import { StatCard, StatGrid } from '@/components/ui/StatCard'
import { useLibrary } from '@/hooks/useLibrary'
import { trialInfo, trialPhaseRank, type OutcomeMeasure, type TrialInfo } from '@/lib/evidence'
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
  const [compare, setCompare] = useState<string[]>([])
  const toggleCompare = (id: string) =>
    setCompare((c) => (c.includes(id) ? c.filter((x) => x !== id) : c.length >= 4 ? c : [...c, id]))

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
        <TrialTable
          rows={filtered.slice((current - 1) * PAGE_SIZE, current * PAGE_SIZE)}
          total={filtered.length}
          page={current}
          pages={pages}
          onPage={setPage}
          compare={compare}
          onCompare={toggleCompare}
        />
      )}

      {compare.length > 0 && (
        <CompareTrials
          trials={compare.map((id) => trials.find((t) => t.record.record_id === id)).filter((t): t is { record: LibraryRecord; info: TrialInfo } => !!t)}
          onRemove={toggleCompare}
          onClear={() => setCompare([])}
        />
      )}

      {trials.length > 0 && (
        <div className="grid gap-6 lg:grid-cols-[minmax(0,1.6fr)_minmax(0,1fr)]">
          <Timeline trials={filtered} />
          <div className="space-y-6">
            <Distribution title="Lead sponsors" subtitle="Top sponsors of the trials shown" counts={count(filtered.map((t) => t.info.sponsor ?? 'Not recorded'))} limit={8} />
            <Distribution title="Recruitment status" subtitle="As registered" counts={count(filtered.map((t) => t.info.status))} limit={8} />
          </div>
        </div>
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
  compare,
  onCompare,
}: {
  rows: { record: LibraryRecord; info: TrialInfo }[]
  total: number
  page: number
  pages: number
  onPage: (p: number) => void
  compare: string[]
  onCompare: (id: string) => void
}) {
  return (
    <div className={table.wrap}>
      <table className={table.table}>
        <thead className={table.head}>
          <tr>
            <th className={`${table.th} w-10`}>
              <span className="sr-only">Compare</span>
            </th>
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
            <tr key={record.record_id} className={cn(table.row, compare.includes(record.record_id) && 'bg-accent-50/50')}>
              <td className={table.td}>
                <input
                  type="checkbox"
                  checked={compare.includes(record.record_id)}
                  disabled={!compare.includes(record.record_id) && compare.length >= 4}
                  onChange={() => onCompare(record.record_id)}
                  aria-label={`Compare ${info.nctId}`}
                  className="h-4 w-4 accent-teal-600"
                />
              </td>
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
          Showing {rows.length} of {total} trials · Source: ClinicalTrials.gov registry data · Tick up to 4 trials to compare
        </span>
        <Pager page={page} pages={pages} onChange={onPage} />
      </div>
    </div>
  )
}

function count(values: string[]): [string, number][] {
  const m = new Map<string, number>()
  for (const v of values) m.set(v, (m.get(v) ?? 0) + 1)
  return [...m.entries()].sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]))
}

function Distribution({ title, subtitle, counts, limit }: { title: string; subtitle: string; counts: [string, number][]; limit: number }) {
  const max = Math.max(1, ...counts.map(([, n]) => n))
  const rest = counts.slice(limit).reduce((s, [, n]) => s + n, 0)
  return (
    <Panel title={title} subtitle={subtitle}>
      <ul className="space-y-2">
        {counts.slice(0, limit).map(([label, n]) => (
          <li key={label} className="grid grid-cols-[minmax(0,9rem)_1fr_2rem] items-center gap-3 text-[13px]">
            <span className="truncate text-slate-600" title={label}>
              {label}
            </span>
            <span className="h-2.5 rounded-full bg-slate-100">
              <span className="block h-2.5 rounded-full bg-accent-600" style={{ width: `${(n / max) * 100}%` }} />
            </span>
            <span className="text-right font-medium tabular-nums text-ink-900">{n}</span>
          </li>
        ))}
      </ul>
      {rest > 0 && <p className="mt-3 text-xs text-slate-500">+ {rest} more across {counts.length - limit} others</p>}
    </Panel>
  )
}

function yearFraction(date: string | null): number | null {
  if (!date) return null
  const [y, m] = date.split('-').map((x) => Number.parseInt(x, 10))
  return Number.isFinite(y) ? y + ((Number.isFinite(m) ? m : 1) - 1) / 12 : null
}

function Timeline({ trials }: { trials: { record: LibraryRecord; info: TrialInfo }[] }) {
  const [now] = useState(() => {
    const d = new Date()
    return d.getFullYear() + d.getMonth() / 12
  })
  const rows = trials
    .map((t) => ({ ...t, start: yearFraction(t.info.startDate), end: yearFraction(t.info.completionDate) }))
    .filter((t): t is typeof t & { start: number } => t.start !== null)
    .sort((a, b) => a.start - b.start)
    .slice(-14)
  if (!rows.length) {
    return (
      <Panel title="Trial timeline">
        <p className="text-sm text-slate-500">None of the trials shown record a start date.</p>
      </Panel>
    )
  }
  const min = Math.floor(Math.min(...rows.map((r) => r.start)))
  const max = Math.ceil(Math.max(...rows.map((r) => r.end ?? r.start + 0.5), now + 0.5))
  const span = Math.max(1, max - min)
  const pct = (v: number) => `${((v - min) / span) * 100}%`
  const ticks = Array.from({ length: span + 1 }, (_, i) => min + i).filter((_, i, a) => a.length <= 12 || i % Math.ceil(a.length / 10) === 0)
  return (
    <Panel title="Trial timeline" subtitle={`Start to completion as registered · ${rows.length} most recent starts of the trials shown · lighter bars are estimated dates`}>
      <div className="relative">
        <div className="relative ml-[7.5rem] h-5 border-b border-slate-200 text-[10px] text-slate-500">
          {ticks.map((t) => (
            <span key={t} className="absolute -translate-x-1/2" style={{ left: pct(t) }}>
              {t}
            </span>
          ))}
        </div>
        <ul className="mt-2 space-y-1.5">
          {rows.map(({ record, info, start, end }) => {
            const estimated = (info.completionType ?? '').toLowerCase().includes('estimated')
            return (
              <li key={record.record_id} className="grid grid-cols-[7rem_1fr] items-center gap-2 text-[11px]">
                <a href={record.source_url} target="_blank" rel="noreferrer" className="truncate font-mono text-slate-600 hover:text-accent-700" title={record.title}>
                  {info.nctId}
                </a>
                <span className="relative h-3">
                  <span
                    className={cn('absolute h-3 rounded-sm', estimated ? 'bg-accent-200' : 'bg-accent-600')}
                    style={{ left: pct(start), width: `max(4px, calc(${pct(end ?? start + 0.1)} - ${pct(start)}))` }}
                    title={`${info.startDate ?? '?'} → ${info.completionDate ?? 'no completion date'}${estimated ? ' (estimated)' : ''} · ${info.status}`}
                  />
                </span>
              </li>
            )
          })}
        </ul>
        {now >= min && now <= max && <span className="pointer-events-none absolute bottom-0 top-5 border-l border-dashed border-rose-400" style={{ left: `calc(7.5rem + (100% - 7.5rem) * ${(now - min) / span})` }} aria-hidden="true" />}
      </div>
      <p className="mt-3 text-xs text-slate-500">Dashed line: today. Dates come from the registry; estimated completion dates are plans, not outcomes.</p>
    </Panel>
  )
}

function Outcomes({ items, count }: { items: OutcomeMeasure[]; count?: number }) {
  if (!items.length) return <span className="text-slate-400">{count ? `${count} registered (not captured)` : 'None registered'}</span>
  return (
    <ul className="list-disc space-y-1 pl-4">
      {items.map((o) => (
        <li key={o.measure}>
          {o.measure}
          {o.timeFrame && <span className="text-slate-500"> · {o.timeFrame}</span>}
        </li>
      ))}
      {count !== undefined && count > items.length && <li className="list-none text-slate-500">+ {count - items.length} more on the registry</li>}
    </ul>
  )
}

function CompareTrials({
  trials,
  onRemove,
  onClear,
}: {
  trials: { record: LibraryRecord; info: TrialInfo }[]
  onRemove: (id: string) => void
  onClear: () => void
}) {
  const rows: { label: string; render: (t: { record: LibraryRecord; info: TrialInfo }) => React.ReactNode }[] = [
    { label: 'Status', render: ({ info }) => <span className={cn('inline-block rounded px-2 py-0.5', statusTone(info.statusRaw))}>{info.status}</span> },
    { label: 'Phase', render: ({ info }) => info.phases.join(', ') || 'Not applicable / not recorded' },
    { label: 'Study design', render: ({ info }) => [info.studyType, info.allocation !== 'Na' ? info.allocation : null, info.masking && `masking: ${info.masking.toLowerCase()}`, info.purpose && `purpose: ${info.purpose.toLowerCase()}`].filter(Boolean).join(' · ') || 'Not recorded' },
    { label: 'Enrolment', render: ({ info }) => (info.enrollment !== null ? `${info.enrollment.toLocaleString()} ${info.enrollmentType ? `(${info.enrollmentType.toLowerCase()})` : ''}` : 'Not reported') },
    { label: 'Conditions', render: ({ info }) => info.conditions.join(', ') || 'Not recorded' },
    { label: 'Interventions', render: ({ info }) => info.interventions.join(', ') || 'Not recorded' },
    { label: 'Lead sponsor', render: ({ info }) => info.sponsor ?? 'Not recorded' },
    { label: 'Start', render: ({ info }) => info.startDate ?? 'Not recorded' },
    { label: 'Completion', render: ({ info }) => (info.completionDate ? `${info.completionDate}${info.completionType ? ` (${info.completionType.toLowerCase()})` : ''}` : 'Not recorded') },
    { label: 'Primary outcome measures', render: ({ info }) => <Outcomes items={info.primaryOutcomes} /> },
    { label: 'Secondary outcome measures', render: ({ info }) => <Outcomes items={info.secondaryOutcomes} count={info.secondaryOutcomeCount} /> },
    {
      label: 'Results',
      render: ({ record, info }) =>
        info.hasResults ? (
          <span>
            Results posted on ClinicalTrials.gov{info.resultsFirstPosted ? ` (${info.resultsFirstPosted})` : ''}. PharmaLens does not retrieve result values —{' '}
            <a href={`${record.source_url}?tab=results`} target="_blank" rel="noreferrer" className="text-accent-700 hover:underline">
              view on the registry
            </a>
            .
          </span>
        ) : (
          <span className="text-slate-500">No results posted on the registry.</span>
        ),
    },
    { label: 'Reason stopped', render: ({ info }) => info.whyStopped ?? '—' },
  ]
  return (
    <Panel
      title={`Comparing ${trials.length} ${trials.length === 1 ? 'trial' : 'trials'}`}
      subtitle="Registered information from ClinicalTrials.gov. Outcome measures are what each trial planned to measure, not its results."
      actions={
        <button type="button" onClick={onClear} className="text-xs font-medium text-accent-700 hover:underline">
          Clear
        </button>
      }
      bodyClassName="overflow-x-auto p-0"
    >
      {trials.length < 2 && <p className="px-5 pb-2 text-xs text-slate-500">Tick at least one more trial in the table to compare side by side.</p>}
      <table className="w-full min-w-[40rem] table-fixed text-left text-xs">
        <thead>
          <tr className="border-y border-slate-100 bg-slate-50">
            <th className="w-40 px-4 py-2.5 font-semibold text-slate-500">Field</th>
            {trials.map(({ record, info }) => (
              <th key={record.record_id} className="px-4 py-2.5 align-top font-normal">
                <div className="flex items-start justify-between gap-2">
                  <a href={record.source_url} target="_blank" rel="noreferrer" className="font-mono font-semibold text-ink-900 hover:text-accent-700">
                    {info.nctId}
                  </a>
                  <button type="button" onClick={() => onRemove(record.record_id)} aria-label={`Remove ${info.nctId}`} className="text-slate-400 hover:text-ink-900">
                    <X className="h-3.5 w-3.5" aria-hidden="true" />
                  </button>
                </div>
                <p className="mt-1 line-clamp-3 text-slate-600">{record.title}</p>
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.label} className="border-b border-slate-100 align-top">
              <th scope="row" className="px-4 py-2.5 font-medium text-slate-600">
                {row.label}
              </th>
              {trials.map((t) => (
                <td key={t.record.record_id} className="break-words px-4 py-2.5 text-ink-900">
                  {row.render(t)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </Panel>
  )
}
