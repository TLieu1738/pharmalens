// Sessions started in this browser (useful for signed-out demo sessions, which are not listed server-side).
import type { SessionStatus } from '@/types/research'

const KEY = 'pharmalens.recentSessions.v1'
const MAX = 20

export interface RecentSession {
  session_id: string
  research_question: string
  created_at: string
  status?: SessionStatus
}

export function loadRecentSessions(): RecentSession[] {
  try {
    const raw = window.localStorage.getItem(KEY)
    const parsed = raw ? (JSON.parse(raw) as RecentSession[]) : []
    return Array.isArray(parsed) ? parsed : []
  } catch {
    return []
  }
}

export function rememberSession(entry: RecentSession): void {
  try {
    const next = [entry, ...loadRecentSessions().filter((s) => s.session_id !== entry.session_id)].slice(0, MAX)
    window.localStorage.setItem(KEY, JSON.stringify(next))
  } catch {
    /* storage unavailable — non-critical */
  }
}

export function updateRecentStatus(sessionId: string, status: SessionStatus): void {
  try {
    const list = loadRecentSessions()
    const item = list.find((s) => s.session_id === sessionId)
    if (item && item.status !== status) {
      item.status = status
      window.localStorage.setItem(KEY, JSON.stringify(list))
    }
  } catch {
    /* non-critical */
  }
}
