import { ArrowRight } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { ResearchQuestionForm } from '@/components/research/ResearchQuestionForm'
import { StatusBadge } from '@/components/research/StatusBadge'
import { table } from '@/components/ui/styles'
import { PageHeader } from '@/components/ui/PageHeader'
import { Panel } from '@/components/ui/Panel'
import { StatCard, StatGrid } from '@/components/ui/StatCard'
import { invalidateLibrary, useLibrary } from '@/hooks/useLibrary'
import { useMySessions } from '@/hooks/useMySessions'
import { retrievalOutcomes } from '@/lib/evidence'
import { SOURCE_LABELS, formatDate } from '@/lib/labels'
import { rememberSession } from '@/lib/recentSessions'
import { cn } from '@/lib/utils'
import { api, ApiError } from '@/services/api'
import type { SessionDetail, SourceName } from '@/types/research'

const SOURCES: { id: SourceName; detail: string }[] = [
  { id: 'pubmed', detail: 'Publications & abstracts' },
  { id: 'europe_pmc', detail: 'Literature incl. preprints' },
  { id: 'clinicaltrials_gov', detail: 'Registered studies' },
  { id: 'chembl', detail: 'Compounds & mechanisms' },
  { id: 'open_targets', detail: 'Disease–target associations' },
  { id: 'openalex', detail: 'Citations, institutions and topics' },
  { id: 'pubchem', detail: 'Chemical identifiers by InChIKey' },
]

/** Executive-summary highlights from the user's most recent completed sessions. */
function useRecentInsights(sessionIds: string[]) {
  const [insights, setInsights] = useState<SessionDetail[] | null>(null)
  const key = sessionIds.join(',')
  useEffect(() => {
    if (!key) return
    let cancelled = false
    Promise.all(key.split(',').map((id) => api.getSession(id)))
      .then((rows) => !cancelled && setInsights(rows))
      .catch(() => !cancelled && setInsights([]))
    return () => {
      cancelled = true
    }
  }, [key])
  return key ? insights : []
}

interface SourceCoverage {
  retrieved: number
  matching: number | null // source-reported matches, summed across queries; null if the source gives no count
  queries: number
  failed: boolean
}

/** Per-source coverage of one completed run, from the searches each agent recorded. */
function coverageBySource(session: SessionDetail | undefined): Map<string, SourceCoverage> {
  const out = new Map<string, SourceCoverage>()
  if (!session) return out
  for (const o of retrievalOutcomes(session)) {
    const c = out.get(o.source) ?? { retrieved: 0, matching: null, queries: 0, failed: true }
    c.queries += 1
    c.retrieved += o.record_count
    c.failed = c.failed && !o.ok
    if (typeof o.total_available === 'number') c.matching = (c.matching ?? 0) + o.total_available
    out.set(o.source, c)
  }
  return out
}

export default function Dashboard() {
  const navigate = useNavigate()
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const { items: sessions } = useMySessions()
  const { records } = useLibrary()

  const perSession = useMemo(() => {
    const counts = new Map<string, number>()
    for (const r of records ?? []) for (const s of r.sessions) counts.set(s.session_id, (counts.get(s.session_id) ?? 0) + 1)
    return counts
  }, [records])
  const count = (pred: (c: string) => boolean) => (records ? records.filter((r) => pred(r.category)).length : '—')
  const perSource = (id: SourceName) => (records ?? []).filter((r) => r.source_name === id || r.also_found_in.includes(id)).length

  const completedIds = (sessions ?? []).filter((s) => s.status === 'completed').slice(0, 2).map((s) => s.session_id)
  const insights = useRecentInsights(completedIds)
  const latest = coverageBySource(insights?.[0])

  const start = async (question: string) => {
    setSubmitting(true)
    setError(null)
    try {
      const { session_id, status } = await api.createResearch(question)
      rememberSession({ session_id, research_question: question, created_at: new Date().toISOString(), status })
      invalidateLibrary()
      navigate(`/research/${session_id}`)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not start research.')
      setSubmitting(false)
    }
  }

  return (
    <div className="space-y-8">
      <PageHeader
        eyebrow="Welcome back"
        title="Research intelligence, powered by evidence."
        subtitle="PharmaLens connects scientific literature, clinical trials and molecular data to help you investigate with confidence."
      />

      <ResearchQuestionForm onSubmit={start} submitting={submitting} error={error} />

      <StatGrid>
        <StatCard label="Research sessions" value={sessions ? sessions.length : '—'} />
        <StatCard label="Publications analysed" value={count((c) => c === 'literature')} />
        <StatCard label="Clinical trials identified" value={count((c) => c === 'clinical_trial')} />
        <StatCard label="Compounds indexed" value={records ? records.filter((r) => r.source_name === 'chembl').length : '—'} />
      </StatGrid>

      <Panel
        title="Recent research activity"
        actions={
          <Link to="/saved" className="text-[13px] font-medium text-accent-700 hover:underline">
            View all sessions →
          </Link>
        }
        bodyClassName="p-0 pt-4"
      >
        {!sessions?.length ? (
          <p className="px-5 pb-5 text-sm text-slate-500">No research yet. Ask a question above to start your first session.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className={table.table}>
              <thead className={table.head}>
                <tr>
                  <th className={table.th}>Research topic</th>
                  <th className={table.th}>Date</th>
                  <th className={table.th}>Records retrieved</th>
                  <th className={table.th}>Status</th>
                  <th className={`${table.th} text-right`}>Actions</th>
                </tr>
              </thead>
              <tbody>
                {sessions.slice(0, 5).map((s) => (
                  <tr key={s.session_id} className={table.row}>
                    <td className={`${table.td} max-w-md`}>
                      <p className="line-clamp-2 text-ink-900">{s.research_question}</p>
                    </td>
                    <td className={`${table.td} whitespace-nowrap text-slate-500`}>{formatDate(s.created_at)}</td>
                    <td className={`${table.td} tabular-nums`}>{records ? (perSession.get(s.session_id) ?? 0) : '—'}</td>
                    <td className={table.td}>
                      <StatusBadge status={s.status ?? 'pending'} />
                    </td>
                    <td className={`${table.td} text-right`}>
                      <Link to={`/research/${s.session_id}`} className="inline-block rounded-md border border-slate-200 px-4 py-1.5 text-[13px] font-medium text-ink-900 hover:border-slate-300">
                        {s.status === 'completed' ? 'Reopen' : 'View'}
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Panel>

      <div className="grid gap-6 lg:grid-cols-[minmax(0,1.5fr)_minmax(0,1fr)]">
        <Panel
          title="Data sources"
          subtitle="Records in your library, and what your latest run took versus what matched at each source"
          actions={<span className="text-xs text-slate-500">Public APIs · queried at request time</span>}
        >
          <ul className="grid gap-x-6 gap-y-4 sm:grid-cols-2 lg:grid-cols-3">
            {SOURCES.map((s) => {
              const run = latest.get(s.id)
              return (
                <li key={s.id}>
                  <p className="text-sm font-medium text-ink-900">{SOURCE_LABELS[s.id]}</p>
                  <p className="text-xs text-slate-500">{s.detail}</p>
                  <p className="mt-1.5 inline-flex items-center gap-1.5 rounded bg-emerald-50 px-2 py-0.5 text-xs text-emerald-700">
                    <span className="h-1.5 w-1.5 rounded-full bg-emerald-500" aria-hidden="true" />
                    Live · {records ? perSource(s.id) : '—'} in your library
                  </p>
                  {run && (
                    <p
                      className={cn('mt-1 text-[11px]', run.failed ? 'text-rose-700' : 'text-slate-500')}
                      title={run.queries > 1 ? 'Matching counts are added across queries, so records matched by more than one query are counted more than once.' : undefined}
                    >
                      {run.failed
                        ? 'Latest run: source unavailable'
                        : run.matching !== null
                          ? `Latest run: ${run.retrieved.toLocaleString()} of ${run.matching.toLocaleString()} matching${run.queries > 1 ? ` · ${run.queries} queries` : ''}`
                          : `Latest run: ${run.retrieved.toLocaleString()} retrieved`}
                    </p>
                  )}
                </li>
              )
            })}
          </ul>
        </Panel>

        <Panel title="Recent insights" subtitle="From your completed research sessions">
          {insights === null ? (
            <p className="text-sm text-slate-500">Loading…</p>
          ) : insights.length === 0 ? (
            <p className="text-sm text-slate-500">Insights appear here once a research session completes.</p>
          ) : (
            <ul className="space-y-4">
              {insights.map((s) => {
                const first = s.report?.sections[0]?.statements[0]
                return (
                  <li key={s.session_id}>
                    <p className="line-clamp-1 text-sm font-medium text-ink-900">{s.research_question}</p>
                    {first && <p className="mt-1 line-clamp-3 text-[13px] leading-relaxed text-slate-600">{first.text}</p>}
                    <Link to={`/research/${s.session_id}`} className="mt-1 inline-flex items-center gap-1 text-[13px] font-medium text-accent-700 hover:underline">
                      Review the source-level evidence <ArrowRight className="h-3.5 w-3.5" aria-hidden="true" />
                    </Link>
                  </li>
                )
              })}
            </ul>
          )}
        </Panel>
      </div>
    </div>
  )
}
