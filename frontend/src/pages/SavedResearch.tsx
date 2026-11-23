import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { StatusBadge } from '@/components/research/StatusBadge'
import { EmptyState, FilterBar, SearchInput, Select } from '@/components/ui/Controls'
import { buttonPrimary, table } from '@/components/ui/styles'
import { PageHeader } from '@/components/ui/PageHeader'
import { useLibrary } from '@/hooks/useLibrary'
import { useMySessions } from '@/hooks/useMySessions'
import { formatDate } from '@/lib/labels'

type StatusFilter = 'all' | 'completed' | 'in_progress' | 'failed'

export default function SavedResearch() {
  const { items, error } = useMySessions()
  const { records } = useLibrary()
  const [query, setQuery] = useState('')
  const [status, setStatus] = useState<StatusFilter>('all')

  const counts = useMemo(() => {
    const m = new Map<string, { total: number; trials: number; pubs: number }>()
    for (const r of records ?? [])
      for (const s of r.sessions) {
        const c = m.get(s.session_id) ?? { total: 0, trials: 0, pubs: 0 }
        c.total += 1
        if (r.category === 'clinical_trial') c.trials += 1
        if (r.category === 'literature') c.pubs += 1
        m.set(s.session_id, c)
      }
    return m
  }, [records])

  const filtered = (items ?? []).filter((s) => {
    const matchesStatus =
      status === 'all' || (status === 'in_progress' ? s.status !== 'completed' && s.status !== 'failed' : s.status === status)
    return matchesStatus && s.research_question.toLowerCase().includes(query.toLowerCase())
  })

  return (
    <div className="space-y-6">
      <PageHeader
        crumbs={[{ label: 'Workspace', to: '/' }, { label: 'Saved research' }]}
        title="Saved Research"
        subtitle="Every research session is saved to your account. Reopen a briefing to review its evidence and citations."
        actions={
          <Link to="/" className={buttonPrimary}>
            New research
          </Link>
        }
      />

      <FilterBar>
        <SearchInput value={query} onChange={setQuery} placeholder="Search your research questions…" className="min-w-[16rem] flex-[2]" />
        <Select
          label="Status"
          value={status}
          onChange={setStatus}
          options={[
            { value: 'all', label: 'All statuses' },
            { value: 'completed', label: 'Completed' },
            { value: 'in_progress', label: 'In progress' },
            { value: 'failed', label: 'Failed' },
          ]}
        />
      </FilterBar>

      {error ? (
        <p className="text-sm text-rose-700">{error}</p>
      ) : !items ? (
        <p className="text-sm text-slate-500">Loading…</p>
      ) : !items.length ? (
        <EmptyState title="No research saved yet">
          <Link to="/" className="font-medium text-accent-700 hover:underline">
            Ask your first question
          </Link>{' '}
          to create a source-linked briefing.
        </EmptyState>
      ) : filtered.length === 0 ? (
        <EmptyState title="No sessions match these filters" />
      ) : (
        <div className={table.wrap}>
          <table className={table.table}>
            <thead className={table.head}>
              <tr>
                <th className={table.th}>Research question</th>
                <th className={table.th}>Started</th>
                <th className={table.th}>Evidence</th>
                <th className={table.th}>Status</th>
                <th className={table.th}>
                  <span className="sr-only">Open</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((s) => {
                const c = counts.get(s.session_id)
                return (
                  <tr key={s.session_id} className={table.row}>
                    <td className={`${table.td} max-w-xl`}>
                      <Link to={`/research/${s.session_id}`} className="line-clamp-2 font-medium text-ink-900 hover:text-accent-700">
                        {s.research_question}
                      </Link>
                    </td>
                    <td className={`${table.td} whitespace-nowrap text-slate-500`}>{formatDate(s.created_at, true)}</td>
                    <td className={`${table.td} whitespace-nowrap text-slate-600`}>
                      {c ? (
                        <>
                          <span className="font-medium tabular-nums text-ink-900">{c.total}</span> records
                          <p className="text-xs text-slate-500">
                            {c.pubs} publications · {c.trials} trials
                          </p>
                        </>
                      ) : (
                        '—'
                      )}
                    </td>
                    <td className={table.td}>
                      <StatusBadge status={s.status ?? 'pending'} />
                    </td>
                    <td className={`${table.td} text-right`}>
                      <Link to={`/research/${s.session_id}`} className="inline-block rounded-md border border-slate-200 px-4 py-1.5 text-[13px] font-medium text-ink-900 hover:border-slate-300">
                        {s.status === 'completed' ? 'Reopen' : 'View'}
                      </Link>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
