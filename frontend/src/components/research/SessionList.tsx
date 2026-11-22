import { ChevronRight } from 'lucide-react'
import { Link } from 'react-router-dom'
import { formatDate } from '@/lib/labels'
import type { SessionStatus } from '@/types/research'
import { StatusBadge } from './StatusBadge'

export interface SessionListItem {
  session_id: string
  research_question: string
  created_at: string
  status?: SessionStatus
}

export function SessionList({ items, empty }: { items: SessionListItem[]; empty: string }) {
  if (!items.length) {
    return <p className="rounded-lg border border-dashed border-slate-300 bg-white px-4 py-8 text-center text-sm text-slate-500">{empty}</p>
  }
  return (
    <ul className="divide-y divide-slate-100 rounded-lg border border-slate-200 bg-white">
      {items.map((s) => (
        <li key={s.session_id}>
          <Link to={`/research/${s.session_id}`} className="group flex items-center gap-3 px-4 py-3 hover:bg-slate-50">
            <div className="min-w-0 flex-1">
              <p className="truncate text-sm font-medium text-ink-900">{s.research_question}</p>
              <p className="mt-0.5 text-xs text-slate-500">{formatDate(s.created_at, true)}</p>
            </div>
            {s.status && <StatusBadge status={s.status} />}
            <ChevronRight className="h-4 w-4 text-slate-300 group-hover:text-slate-500" aria-hidden="true" />
          </Link>
        </li>
      ))}
    </ul>
  )
}
