import { Download, Loader2, Plus } from 'lucide-react'
import { Link, Navigate, useParams } from 'react-router-dom'
import { AgentStrip } from '@/components/research/AgentStrip'
import { StatusBadge } from '@/components/research/StatusBadge'
import { EmptyState } from '@/components/ui/Controls'
import { buttonSecondary } from '@/components/ui/styles'
import { PageHeader } from '@/components/ui/PageHeader'
import { useMySessions } from '@/hooks/useMySessions'
import { useResearchSession } from '@/hooks/useResearchSession'
import { downloadText, reportToMarkdown } from '@/lib/exportMarkdown'
import { formatDate } from '@/lib/labels'
import ResearchResults from './ResearchResults'
import ResearchWorkspace from './ResearchWorkspace'

export default function ResearchSession() {
  const { sessionId } = useParams()
  return <ResearchSessionView key={sessionId} sessionId={sessionId} />
}

/** /research without an ID opens the most recent session. */
export function LatestResearch() {
  const { items, error } = useMySessions()
  if (error) return <p className="text-sm text-rose-700">{error}</p>
  if (!items) return <p className="text-sm text-slate-500">Loading…</p>
  if (items.length) return <Navigate to={`/research/${items[0].session_id}`} replace />
  return (
    <div className="space-y-6">
      <PageHeader crumbs={[{ label: 'Workspace', to: '/' }, { label: 'Research' }]} title="Research Workspace" />
      <EmptyState title="No research sessions yet">
        <Link to="/" className="font-medium text-accent-700 hover:underline">
          Ask your first research question
        </Link>{' '}
        to see agents retrieve and synthesise evidence here.
      </EmptyState>
    </div>
  )
}

function ResearchSessionView({ sessionId }: { sessionId: string | undefined }) {
  const { data, error, loading } = useResearchSession(sessionId)

  if (loading && !data) {
    return (
      <div className="flex items-center gap-2 py-20 text-sm text-slate-500">
        <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" /> Loading research session…
      </div>
    )
  }
  if (error && !data) {
    return (
      <EmptyState title={error.status === 404 ? 'Session not found' : 'Could not load session'}>
        {error.status === 404 ? 'It may belong to another account, or the link is incorrect.' : error.message}{' '}
        <Link to="/" className="font-medium text-accent-700 hover:underline">
          Start new research
        </Link>
      </EmptyState>
    )
  }
  if (!data) return null

  const completed = data.status === 'completed' && data.report
  const plan = data.research_plan
  const scope = plan
    ? [plan.disease_area, plan.biological_targets.slice(0, 3).join(', '), plan.compounds.slice(0, 3).join(', ')].filter(Boolean).join(' · ')
    : null

  return (
    <div className="space-y-6">
      <PageHeader
        crumbs={[{ label: 'Workspace', to: '/' }, { label: 'Research', to: '/saved' }, { label: plan?.disease_area ?? 'Session' }]}
        title="Research Workspace"
        subtitle="A structured, source-grounded investigation. You stay in control of the conclusion."
        actions={
          <>
            <Link to="/" className={buttonSecondary}>
              <Plus className="h-4 w-4" aria-hidden="true" /> New
            </Link>
            {completed && (
              <button onClick={() => downloadText(`pharmalens-${data.session_id.slice(0, 8)}.md`, reportToMarkdown(data))} className={buttonSecondary}>
                <Download className="h-4 w-4" aria-hidden="true" /> Export report
              </button>
            )}
          </>
        }
      />

      <section className="rounded-lg border border-slate-200 bg-white px-5 py-4">
        <p className="text-[15px] leading-relaxed text-ink-900">{data.research_question}</p>
        <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1.5 text-[13px] text-slate-500">
          <StatusBadge status={data.status} />
          {scope && <span>{scope}</span>}
          <span>· Started {formatDate(data.created_at, true)}</span>
          {data.completed_at && <span>· Evidence retrieved live, finished {formatDate(data.completed_at, true)}</span>}
        </div>
        {error && <p className="mt-2 text-xs text-amber-700">Connection issue while refreshing: {error.message}</p>}
      </section>

      <AgentStrip agents={data.agents} />

      {completed ? <ResearchResults session={data} /> : <ResearchWorkspace session={data} />}
    </div>
  )
}
