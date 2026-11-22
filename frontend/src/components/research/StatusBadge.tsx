import { Badge, type BadgeTone } from '@/components/ui/Badge'
import { STATUS_LABELS } from '@/lib/labels'
import type { SessionStatus } from '@/types/research'

export function StatusBadge({ status }: { status: SessionStatus }) {
  const tone: BadgeTone = status === 'completed' ? 'success' : status === 'failed' ? 'danger' : 'accent'
  return <Badge tone={tone}>{STATUS_LABELS[status]}</Badge>
}
