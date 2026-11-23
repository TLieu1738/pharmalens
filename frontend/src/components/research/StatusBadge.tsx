import { STATUS_LABELS } from '@/lib/labels'
import { cn } from '@/lib/utils'
import type { SessionStatus } from '@/types/research'

export function StatusBadge({ status, className }: { status: SessionStatus; className?: string }) {
  const tone =
    status === 'completed'
      ? 'bg-emerald-50 text-emerald-700'
      : status === 'failed'
        ? 'bg-rose-50 text-rose-700'
        : 'bg-accent-50 text-accent-700'
  return (
    <span className={cn('inline-flex items-center rounded px-2.5 py-1 text-xs font-medium', tone, className)}>
      {status === 'completed' || status === 'failed' ? STATUS_LABELS[status] : 'In progress'}
    </span>
  )
}
