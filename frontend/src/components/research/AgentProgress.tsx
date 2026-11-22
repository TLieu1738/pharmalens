import { AlertTriangle, CheckCircle2, Circle, Loader2, MinusCircle, XCircle } from 'lucide-react'
import { AGENT_LABELS, SOURCE_LABELS, formatDuration } from '@/lib/labels'
import { cn } from '@/lib/utils'
import type { AgentExecution, ExecutionStatus, SourceName } from '@/types/research'

const ICONS: Record<ExecutionStatus, { icon: typeof Circle; cls: string; label: string }> = {
  pending: { icon: Circle, cls: 'text-slate-300', label: 'Waiting' },
  running: { icon: Loader2, cls: 'animate-spin text-accent-600', label: 'Running' },
  completed: { icon: CheckCircle2, cls: 'text-emerald-600', label: 'Completed' },
  partial: { icon: AlertTriangle, cls: 'text-amber-500', label: 'Partial' },
  failed: { icon: XCircle, cls: 'text-rose-600', label: 'Failed' },
  skipped: { icon: MinusCircle, cls: 'text-slate-400', label: 'Skipped' },
}

export function AgentProgress({ agents, compact = false }: { agents: AgentExecution[]; compact?: boolean }) {
  return (
    <ol className="divide-y divide-slate-100" aria-label="Agent progress">
      {agents.map((agent) => {
        const meta = ICONS[agent.status]
        const Icon = meta.icon
        const label = AGENT_LABELS[agent.agent_name]
        return (
          <li key={agent.agent_name} className="flex gap-3 py-3 first:pt-0 last:pb-0">
            <Icon className={cn('mt-0.5 h-4 w-4 shrink-0', meta.cls)} aria-label={meta.label} />
            <div className="min-w-0 flex-1">
              <div className="flex flex-wrap items-baseline gap-x-2">
                <p className="text-sm font-medium text-ink-900">{label.name}</p>
                <p className="text-xs text-slate-500">{label.detail}</p>
                <span className="ml-auto font-mono text-[11px] text-slate-400">
                  {agent.record_count != null && `${agent.record_count} rec · `}
                  {agent.status === 'running' ? 'running…' : formatDuration(agent.duration_ms)}
                </span>
              </div>
              {!compact && agent.message && <p className="mt-0.5 text-xs leading-relaxed text-slate-600">{agent.message}</p>}
              {agent.sources.length > 0 && (
                <div className="mt-1.5 flex flex-wrap gap-1.5">
                  {agent.sources.map((s) => (
                    <span
                      key={s.source}
                      title={s.error ?? undefined}
                      className={cn(
                        'rounded border px-1.5 py-0.5 font-mono text-[10.5px]',
                        s.ok ? 'border-slate-200 text-slate-600' : 'border-rose-200 bg-rose-50 text-rose-700',
                      )}
                    >
                      {SOURCE_LABELS[s.source as SourceName] ?? s.source}: {s.ok ? s.record_count : 'unavailable'}
                    </span>
                  ))}
                </div>
              )}
              {agent.error_message && agent.status !== 'partial' && (
                <p className="mt-1 text-xs text-rose-700">{agent.error_message}</p>
              )}
            </div>
          </li>
        )
      })}
    </ol>
  )
}
