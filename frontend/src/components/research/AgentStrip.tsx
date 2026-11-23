import { AlertTriangle, Check, Circle, Loader2, Minus, X } from 'lucide-react'
import { AGENT_LABELS } from '@/lib/labels'
import { cn } from '@/lib/utils'
import type { AgentExecution, ExecutionStatus } from '@/types/research'

const SHORT_NAMES: Record<string, string> = {
  research_planner: 'Planner',
  literature_agent: 'Literature',
  clinical_agent: 'Clinical trials',
  target_agent: 'Targets',
  compound_agent: 'Compounds',
  evidence_validation: 'Validation',
  research_synthesis: 'Synthesis',
}

const STATE: Record<ExecutionStatus, { icon: typeof Check; cls: string }> = {
  pending: { icon: Circle, cls: 'text-slate-300' },
  running: { icon: Loader2, cls: 'animate-spin text-accent-600' },
  completed: { icon: Check, cls: 'text-ink-900' },
  partial: { icon: AlertTriangle, cls: 'text-amber-500' },
  failed: { icon: X, cls: 'text-rose-600' },
  skipped: { icon: Minus, cls: 'text-slate-400' },
}

function detail(a: AgentExecution): string {
  if (a.status === 'pending') return 'Waiting'
  if (a.status === 'running') return a.agent_name === 'research_synthesis' ? 'Building evidence summary' : 'Running…'
  if (a.status === 'failed') return 'Failed'
  if (a.status === 'skipped') return 'Skipped'
  if (a.agent_name === 'research_planner') return 'Plan ready'
  if (a.agent_name === 'research_synthesis') return 'Report written'
  if (a.agent_name === 'evidence_validation') return `${a.record_count ?? 0} records checked`
  return `${a.record_count ?? 0} found${a.status === 'partial' ? ' · partial' : ''}`
}

/** One-line view of every agent's real execution state, from backend execution records. */
export function AgentStrip({ agents }: { agents: AgentExecution[] }) {
  return (
    <section aria-label="Research agents" className="rounded-lg border border-slate-200 bg-white px-5 py-4">
      <p className="text-[10px] font-semibold uppercase tracking-[0.12em] text-slate-500">Research agents</p>
      <ol className="mt-3 grid grid-cols-2 gap-x-6 gap-y-3 sm:grid-cols-4 xl:grid-cols-7">
        {agents.map((a) => {
          const { icon: Icon, cls } = STATE[a.status]
          return (
            <li key={a.agent_name} title={AGENT_LABELS[a.agent_name].name}>
              <p className={cn('flex items-center gap-1.5 text-sm font-medium', a.status === 'running' ? 'text-accent-700' : 'text-ink-900')}>
                <Icon className={cn('h-3.5 w-3.5 shrink-0', cls)} aria-hidden="true" />
                {SHORT_NAMES[a.agent_name]}
              </p>
              <p className="mt-0.5 text-xs text-slate-500">{detail(a)}</p>
            </li>
          )
        })}
      </ol>
    </section>
  )
}
