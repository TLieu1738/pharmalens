import { cn } from '@/lib/utils'
import type { SessionStatus } from '@/types/research'

const BADGES: Partial<Record<SessionStatus, { label: string; cls: string }>> = {
  completed: { label: 'Completed', cls: 'bg-emerald-50 text-emerald-700' },
  failed: { label: 'Failed', cls: 'bg-rose-50 text-rose-700' },
  cancelled: { label: 'Cancelled', cls: 'bg-slate-100 text-slate-600' },
  awaiting_approval: { label: 'Needs approval', cls: 'bg-amber-50 text-amber-800' },
}

export function StatusBadge({ status, className }: { status: SessionStatus; className?: string }) {
  const badge = BADGES[status] ?? { label: 'In progress', cls: 'bg-accent-50 text-accent-700' }
  return <span className={cn('inline-flex items-center rounded px-2.5 py-1 text-xs font-medium', badge.cls, className)}>{badge.label}</span>
}
