import { AlertTriangle, Loader2 } from 'lucide-react'
import { AgentProgress } from '@/components/research/AgentProgress'
import { PlanSummary } from '@/components/research/PlanSummary'
import { Panel } from '@/components/ui/Panel'
import { STATUS_LABELS } from '@/lib/labels'
import type { SessionDetail } from '@/types/research'

/** Live view while agents run. Everything shown comes from backend agent execution records. */
export default function ResearchWorkspace({ session }: { session: SessionDetail }) {
  const failed = session.status === 'failed'
  const done = session.agents.filter((a) => ['completed', 'partial', 'failed', 'skipped'].includes(a.status)).length
  return (
    <div className="grid gap-6 lg:grid-cols-[minmax(0,1.1fr)_minmax(0,1fr)]">
      <Panel
        title="Agent workflow"
        subtitle={failed ? 'Stopped' : `${STATUS_LABELS[session.status]} · ${done} of ${session.agents.length} agents finished`}
        actions={!failed && <Loader2 className="h-4 w-4 animate-spin text-accent-600" aria-label="Running" />}
      >
        {failed && (
          <div className="mb-4 flex gap-2 rounded-md border border-rose-200 bg-rose-50 px-3 py-2.5 text-sm text-rose-800">
            <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
            <div>
              <p className="font-medium">This research session could not be completed.</p>
              {session.error_message && <p className="mt-0.5 text-xs">{session.error_message}</p>}
            </div>
          </div>
        )}
        <AgentProgress agents={session.agents} />
      </Panel>
      <div className="space-y-6">
        <Panel title="Research plan">
          {session.research_plan ? (
            <PlanSummary plan={session.research_plan} />
          ) : (
            <p className="text-sm text-slate-500">{failed ? 'No plan was produced.' : 'The Research Planner is interpreting your question…'}</p>
          )}
        </Panel>
        {session.warnings.length > 0 && (
          <Panel title="Warnings">
            <ul className="list-disc space-y-1 pl-5 text-sm text-slate-700">
              {session.warnings.map((w) => (
                <li key={w}>{w}</li>
              ))}
            </ul>
          </Panel>
        )}
      </div>
    </div>
  )
}
