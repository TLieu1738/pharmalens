import { Check } from 'lucide-react'
import { cn } from '@/lib/utils'
import type { SessionStatus } from '@/types/research'

const STEPS = ['Question', 'Research protocol', 'Your approval', 'Data retrieval', 'Evidence validation', 'Research report'] as const

/** Index of the step currently in progress (steps before it are done). */
function currentStep(status: SessionStatus): number {
  switch (status) {
    case 'pending':
    case 'planning':
      return 1
    case 'awaiting_approval':
      return 2
    case 'queued':
    case 'researching':
      return 3
    case 'validating':
      return 4
    case 'synthesising':
      return 5
    case 'completed':
      return 6
    default:
      return -1
  }
}

export function WorkflowStepper({ status }: { status: SessionStatus }) {
  const current = currentStep(status)
  const stopped = status === 'failed' || status === 'cancelled'
  return (
    <ol aria-label="Research workflow" className="flex flex-wrap items-center gap-x-2 gap-y-2 text-[13px]">
      {STEPS.map((label, i) => {
        const done = !stopped && i < current
        const active = !stopped && i === current
        return (
          <li key={label} className="flex items-center gap-2">
            <span
              className={cn(
                'flex h-6 w-6 shrink-0 items-center justify-center rounded-full border text-[11px] font-semibold',
                done && 'border-accent-600 bg-accent-600 text-white',
                active && 'border-accent-600 bg-accent-50 text-accent-700',
                !done && !active && 'border-slate-300 text-slate-400',
              )}
              aria-hidden="true"
            >
              {done ? <Check className="h-3.5 w-3.5" /> : i + 1}
            </span>
            <span className={cn(active ? 'font-semibold text-ink-900' : done ? 'text-ink-900' : 'text-slate-500')}>
              {label}
              {active && <span className="sr-only"> (current step)</span>}
            </span>
            {i < STEPS.length - 1 && <span className="mx-1 h-px w-6 bg-slate-300" aria-hidden="true" />}
          </li>
        )
      })}
    </ol>
  )
}
