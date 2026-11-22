import { useApiHealth } from '@/hooks/useApiHealth'
import { cn } from '@/lib/utils'

export function ApiStatusBadge() {
  const health = useApiHealth()
  const { label, dot } =
    health.kind === 'loading'
      ? { label: 'Checking API…', dot: 'bg-slate-400' }
      : health.kind === 'offline'
        ? { label: 'API offline', dot: 'bg-rose-500' }
        : health.data.status === 'ok'
          ? { label: 'API online', dot: 'bg-emerald-500' }
          : { label: 'API degraded', dot: 'bg-amber-500' }

  return (
    <span
      className="inline-flex items-center gap-2 rounded-md border border-slate-200 bg-white px-2.5 py-1 text-xs font-medium text-slate-600"
      title={health.kind === 'offline' ? health.message : undefined}
    >
      <span className={cn('h-1.5 w-1.5 rounded-full', dot)} />
      {label}
    </span>
  )
}
