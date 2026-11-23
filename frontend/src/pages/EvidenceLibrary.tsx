import { ArrowUpRight } from 'lucide-react'
import { useMemo, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { EmptyState, FilterBar, Pager, SearchInput, Select } from '@/components/ui/Controls'
import { table } from '@/components/ui/styles'
import { PageHeader } from '@/components/ui/PageHeader'
import { Panel } from '@/components/ui/Panel'
import { useLibrary } from '@/hooks/useLibrary'
import { qualitySummary, year } from '@/lib/evidence'
import { EVIDENCE_TYPE_LABELS, SOURCE_LABELS } from '@/lib/labels'
import { cn, plural } from '@/lib/utils'
import type { EvidenceType, LibraryRecord, SourceName } from '@/types/research'

const PAGE_SIZE = 15
const TONES = {
  success: 'bg-emerald-50 text-emerald-700',
  warn: 'bg-amber-50 text-amber-800',
  danger: 'bg-rose-50 text-rose-700',
  neutral: 'bg-slate-100 text-slate-600',
}

type QualityFilter = 'all' | 'clean' | 'flagged'
type SortKey = 'year' | 'title'

function matches(r: LibraryRecord, q: string): boolean {
  if (!q) return true
  const hay = [r.title, r.journal, r.summary, r.authors.join(' '), r.identifiers.doi, r.identifiers.pmid, r.identifiers.nct_id, r.source_identifier]
    .filter(Boolean)
    .join(' ')
    .toLowerCase()
  return q
    .toLowerCase()
    .split(/\s+/)
    .every((term) => hay.includes(term))
}

export default function EvidenceLibrary() {
  const { records, error } = useLibrary()
  const [params, setParams] = useSearchParams()
  const query = params.get('q') ?? ''
  const [source, setSource] = useState<'all' | SourceName>('all')
  const [type, setType] = useState<'all' | EvidenceType>('all')
  const [quality, setQuality] = useState<QualityFilter>('all')
  const [sort, setSort] = useState<SortKey>('year')
  const [page, setPage] = useState(1)

  const setQuery = (q: string) => {
    setParams(q ? { q } : {}, { replace: true })
    setPage(1)
  }

  const filtered = useMemo(() => {
    const rows = (records ?? []).filter(
      (r) =>
        matches(r, query) &&
        (source === 'all' || r.source_name === source || r.also_found_in.includes(source)) &&
        (type === 'all' || r.evidence_type === type) &&
        (quality === 'all' || (quality === 'flagged') === r.quality_flags.length > 0),
    )
    return rows.sort((a, b) => (sort === 'title' ? a.title.localeCompare(b.title) : (year(b) ?? 0) - (year(a) ?? 0)))
  }, [records, query, source, type, quality, sort])

  const pages = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE))
  const current = Math.min(page, pages)
  const shown = filtered.slice((current - 1) * PAGE_SIZE, current * PAGE_SIZE)
  const presentTypes = [...new Set((records ?? []).map((r) => r.evidence_type))]

  return (
    <div className="space-y-6">
      <PageHeader
        crumbs={[{ label: 'Workspace', to: '/' }, { label: 'Evidence library' }]}
        title="Evidence Library"
        subtitle="A traceable, searchable collection of every record retrieved across your research sessions."
      />

      <FilterBar>
        <SearchInput value={query} onChange={setQuery} placeholder="Search title, author, DOI, PMID or NCT ID…" className="min-w-[16rem] flex-[2]" />
        <Select
          label="Source"
          value={source}
          onChange={(v) => {
            setSource(v)
            setPage(1)
          }}
          options={[{ value: 'all', label: 'All sources' }, ...(Object.keys(SOURCE_LABELS) as SourceName[]).map((s) => ({ value: s, label: SOURCE_LABELS[s] }))]}
        />
        <Select
          label="Evidence type"
          value={type}
          onChange={(v) => {
            setType(v)
            setPage(1)
          }}
          options={[{ value: 'all', label: 'All evidence types' }, ...presentTypes.map((t) => ({ value: t, label: EVIDENCE_TYPE_LABELS[t] }))]}
        />
        <Select
          label="Quality notes"
          value={quality}
          onChange={(v) => {
            setQuality(v)
            setPage(1)
          }}
          options={[
            { value: 'all', label: 'Any quality notes' },
            { value: 'clean', label: 'No issues flagged' },
            { value: 'flagged', label: 'Has quality notes' },
          ]}
        />
      </FilterBar>

      {error ? (
        <p className="text-sm text-rose-700">{error}</p>
      ) : !records ? (
        <p className="text-sm text-slate-500">Loading your evidence…</p>
      ) : !records.length ? (
        <EmptyState title="Your library is empty">
          Records appear here after your first research session.{' '}
          <Link to="/" className="font-medium text-accent-700 hover:underline">
            Start research
          </Link>
        </EmptyState>
      ) : (
        <>
          <div className="flex flex-wrap items-baseline justify-between gap-3">
            <p className="text-base font-semibold text-ink-900">
              {filtered.length.toLocaleString()} {filtered.length === 1 ? 'record' : 'records'}
              <span className="ml-3 text-[13px] font-normal text-slate-500">from {plural(new Set(records.flatMap((r) => r.sessions.map((s) => s.session_id))).size, 'session')}</span>
            </p>
            <label className="text-[13px] text-accent-700">
              Sort:{' '}
              <select value={sort} onChange={(e) => setSort(e.target.value as SortKey)} className="bg-transparent font-medium focus:outline-none">
                <option value="year">Most recent</option>
                <option value="title">Title A–Z</option>
              </select>
            </label>
          </div>

          {filtered.length === 0 ? (
            <EmptyState title="No records match these filters" />
          ) : (
            <div className={table.wrap}>
              <table className={table.table}>
                <thead className={table.head}>
                  <tr>
                    <th className={table.th}>Record</th>
                    <th className={table.th}>Source</th>
                    <th className={table.th}>Evidence type</th>
                    <th className={table.th}>Quality notes</th>
                    <th className={table.th}>Year</th>
                    <th className={table.th}>
                      <span className="sr-only">Open</span>
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {shown.map((r) => {
                    const q = qualitySummary(r)
                    return (
                      <tr key={r.record_id} className={table.row}>
                        <td className={`${table.td} max-w-lg`}>
                          <p className="line-clamp-2 font-medium text-ink-900">{r.title}</p>
                          <p className="mt-0.5 text-xs text-slate-500">
                            {[r.journal, `in ${r.sessions.length} ${r.sessions.length === 1 ? 'session' : 'sessions'}`].filter(Boolean).join(' · ')}
                          </p>
                        </td>
                        <td className={table.td}>
                          <span className="whitespace-nowrap rounded bg-slate-100 px-2 py-1 text-xs text-slate-700">{SOURCE_LABELS[r.source_name]}</span>
                          {r.also_found_in.length > 0 && <p className="mt-1 text-[11px] text-slate-500">+ {r.also_found_in.map((s) => SOURCE_LABELS[s]).join(', ')}</p>}
                        </td>
                        <td className={`${table.td} whitespace-nowrap text-slate-600`}>{EVIDENCE_TYPE_LABELS[r.evidence_type]}</td>
                        <td className={table.td}>
                          <span title={q.detail.join(', ') || undefined} className={cn('inline-block whitespace-nowrap rounded px-2.5 py-1 text-xs', TONES[q.tone])}>
                            {q.label}
                          </span>
                        </td>
                        <td className={`${table.td} tabular-nums text-slate-600`}>{year(r) ?? '—'}</td>
                        <td className={table.td}>
                          <a href={r.source_url} target="_blank" rel="noreferrer" aria-label={`Open ${r.title} at ${SOURCE_LABELS[r.source_name]}`}>
                            <ArrowUpRight className="h-4 w-4 text-accent-600" aria-hidden="true" />
                          </a>
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
              <div className="flex flex-wrap items-center justify-between gap-3 border-t border-slate-100 px-5 py-3 text-xs text-slate-500">
                <span>
                  Showing {(current - 1) * PAGE_SIZE + 1}–{Math.min(current * PAGE_SIZE, filtered.length)} of {filtered.length}
                </span>
                <Pager page={current} pages={pages} onChange={setPage} />
              </div>
            </div>
          )}
        </>
      )}

      <Panel title="What the quality notes mean">
        <p className="text-sm leading-relaxed text-slate-600">
          PharmaLens does not assign confidence scores. The validation agent only records issues it can detect: missing abstracts or dates,
          preprints that are not peer reviewed, trials that stopped early or have no posted results, and withdrawn compounds. A record with
          no issues flagged still needs expert appraisal.
        </p>
      </Panel>
    </div>
  )
}
