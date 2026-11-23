import { Download, FileText, Loader2, Plus, RotateCcw, Square } from 'lucide-react'
import { useState } from 'react'
import { Link, Navigate, useNavigate, useParams } from 'react-router-dom'
import { AgentStrip } from '@/components/research/AgentStrip'
import { ProtocolEditor } from '@/components/research/ProtocolEditor'
import { StatusBadge } from '@/components/research/StatusBadge'
import { WorkflowStepper } from '@/components/research/WorkflowStepper'
import { EmptyState } from '@/components/ui/Controls'
import { PageHeader } from '@/components/ui/PageHeader'
import { buttonSecondary } from '@/components/ui/styles'
import { invalidateLibrary } from '@/hooks/useLibrary'
import { useMySessions } from '@/hooks/useMySessions'
import { useResearchSession } from '@/hooks/useResearchSession'
import { downloadText, reportToMarkdown } from '@/lib/exportMarkdown'
import { STATUS_LABELS, formatDate } from '@/lib/labels'
import { api, ApiError } from '@/services/api'
import type { SessionDetail } from '@/types/research'
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

const RUNNING = new Set(['pending', 'planning', 'queued', 'researching', 'validating', 'synthesising'])

function DraftingProtocol({ status }: { status: string }) {
  return (
    <section className="flex items-start gap-3 rounded-lg border border-slate-200 bg-white px-6 py-8">
      <Loader2 className="mt-0.5 h-5 w-5 animate-spin text-accent-600" aria-hidden="true" />
      <div>
        <p className="font-medium text-ink-900">{status === 'pending' ? 'Waiting for a research worker…' : 'The Research Planner is drafting your protocol…'}</p>
        <p className="mt-1 text-sm text-slate-600">
          It will propose an objective, key questions, search terms, sources and inclusion criteria. Nothing is searched until you approve it.
          This usually takes under 15 seconds; you can leave this page and come back.
        </p>
      </div>
    </section>
  )
}

function ResearchSessionView({ sessionId }: { sessionId: string | undefined }) {
  const navigate = useNavigate()
  const { data, error, loading, refresh, setData } = useResearchSession(sessionId)
  const [actionError, setActionError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

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

  const act = async (fn: () => Promise<SessionDetail | void>) => {
    setBusy(true)
    setActionError(null)
    try {
      const next = await fn()
      if (next) setData(next)
      refresh()
    } catch (err) {
      setActionError(err instanceof ApiError ? err.message : 'Action failed.')
    } finally {
      setBusy(false)
    }
  }
  const rerun = () =>
    act(async () => {
      const { session_id } = await api.rerunSession(data.session_id)
      invalidateLibrary()
      navigate(`/research/${session_id}`)
    })

  const completed = data.status === 'completed' && data.report
  const plan = data.research_plan
  const scope = plan
    ? [plan.disease_area, plan.biological_targets.slice(0, 3).join(', '), plan.compounds.slice(0, 3).join(', ')].filter(Boolean).join(' · ')
    : null
  const retrying = RUNNING.has(data.status) && data.attempts > 1

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
            {RUNNING.has(data.status) && data.status !== 'pending' && data.status !== 'planning' && (
              <button disabled={busy} onClick={() => void act(() => api.cancelSession(data.session_id))} className={buttonSecondary}>
                <Square className="h-4 w-4" aria-hidden="true" /> Cancel run
              </button>
            )}
            {(completed || data.status === 'failed' || data.status === 'cancelled') && plan && (
              <button disabled={busy} onClick={() => void rerun()} className={buttonSecondary}>
                <RotateCcw className="h-4 w-4" aria-hidden="true" /> Re-run with edits
              </button>
            )}
            {completed && (
              <>
                <button onClick={() => downloadText(`pharmalens-${data.session_id.slice(0, 8)}.md`, reportToMarkdown(data))} className={buttonSecondary}>
                  <Download className="h-4 w-4" aria-hidden="true" /> Markdown
                </button>
                <Link to={`/research/${data.session_id}/print`} target="_blank" className={buttonSecondary}>
                  <FileText className="h-4 w-4" aria-hidden="true" /> PDF report
                </Link>
              </>
            )}
          </>
        }
      />

      <section className="space-y-4 rounded-lg border border-slate-200 bg-white px-5 py-4">
        <WorkflowStepper status={data.status} />
        <div className="border-t border-slate-100 pt-3">
          <p className="text-[15px] leading-relaxed text-ink-900">{data.research_question}</p>
          <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1.5 text-[13px] text-slate-500">
            <StatusBadge status={data.status} />
            {retrying && <span className="rounded bg-amber-50 px-2 py-0.5 text-xs text-amber-800">Retrying · attempt {data.attempts}</span>}
            {RUNNING.has(data.status) && <span>{STATUS_LABELS[data.status]}</span>}
            {scope && <span>{scope}</span>}
            <span>· Started {formatDate(data.created_at, true)}</span>
            {data.completed_at && data.status === 'completed' && <span>· Evidence retrieved live, finished {formatDate(data.completed_at, true)}</span>}
          </div>
        </div>
        {error && <p className="text-xs text-amber-700">Connection issue while refreshing: {error.message}</p>}
        {actionError && (
          <p role="alert" className="text-sm text-rose-700">
            {actionError}
          </p>
        )}
      </section>

      {data.status === 'pending' || data.status === 'planning' ? (
        <DraftingProtocol status={data.status} />
      ) : data.status === 'awaiting_approval' && plan ? (
        <ProtocolEditor
          initial={plan}
          onSave={async (p) => {
            await api.saveProtocol(data.session_id, p)
          }}
          onApprove={async (p) => {
            setData(await api.approveProtocol(data.session_id, p))
            invalidateLibrary()
            refresh()
          }}
          onDiscard={async () => {
            setData(await api.cancelSession(data.session_id))
          }}
        />
      ) : (
        <>
          {data.status !== 'cancelled' && <AgentStrip agents={data.agents} />}
          {data.status === 'cancelled' ? (
            <EmptyState title="This research was cancelled">
              {plan ? 'Use “Re-run with edits” to reopen its protocol in a new session.' : 'It was cancelled before a protocol was drafted.'}
            </EmptyState>
          ) : completed ? (
            <ResearchResults session={data} />
          ) : (
            <ResearchWorkspace session={data} />
          )}
        </>
      )}
    </div>
  )
}
