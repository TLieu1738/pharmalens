import { ArrowLeft, Loader2 } from 'lucide-react'
import { Link, useParams } from 'react-router-dom'
import { StatusBadge } from '@/components/research/StatusBadge'
import { useResearchSession } from '@/hooks/useResearchSession'
import { formatDate } from '@/lib/labels'
import ResearchResults from './ResearchResults'
import ResearchWorkspace from './ResearchWorkspace'

export default function ResearchSession() {
  const { sessionId } = useParams()
  return <ResearchSessionView key={sessionId} sessionId={sessionId} />
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
      <div className="py-16 text-center">
        <h1 className="text-lg font-semibold text-ink-900">{error.status === 404 ? 'Session not found' : 'Could not load session'}</h1>
        <p className="mt-1 text-sm text-slate-500">
          {error.status === 404 ? 'It may belong to another account, or the link is incorrect.' : error.message}
        </p>
        <Link to="/" className="mt-4 inline-block text-sm font-medium text-accent-700 hover:underline">
          Start new research
        </Link>
      </div>
    )
  }
  if (!data) return null

  const completed = data.status === 'completed' && data.report
  return (
    <div className="space-y-6">
      <header className="space-y-2">
        <Link to="/" className="inline-flex items-center gap-1 text-xs font-medium text-slate-500 hover:text-ink-900">
          <ArrowLeft className="h-3.5 w-3.5" aria-hidden="true" /> New research
        </Link>
        <h1 className="max-w-4xl text-xl font-semibold leading-snug tracking-tight text-ink-900">{data.research_question}</h1>
        <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-slate-500">
          <StatusBadge status={data.status} />
          <span>Started {formatDate(data.created_at, true)}</span>
          {data.completed_at && <span>· Evidence retrieved live during this run, finished {formatDate(data.completed_at, true)}</span>}
          {data.report && <span>· AI-generated synthesis</span>}
          {data.demo_mode && <span>· Unlisted demo session (anyone with the link can view)</span>}
        </div>
        {error && <p className="text-xs text-amber-700">Connection issue while refreshing: {error.message}</p>}
      </header>
      {completed ? <ResearchResults session={data} /> : <ResearchWorkspace session={data} />}
    </div>
  )
}
