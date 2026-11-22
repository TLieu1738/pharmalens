import { useEffect, useState } from 'react'
import type { SessionListItem } from '@/components/research/SessionList'
import { useAuth } from '@/hooks/useAuth'
import { loadRecentSessions } from '@/lib/recentSessions'
import { api } from '@/services/api'

/**
 * The current user's research sessions: from their account when sign-in is enabled,
 * otherwise (local dev without Supabase) the sessions started in this browser.
 */
export function useMySessions(): { items: SessionListItem[] | null; error: string | null } {
  const auth = useAuth()
  const [items, setItems] = useState<SessionListItem[] | null>(auth.enabled ? null : loadRecentSessions())
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!auth.enabled || !auth.session) return
    let cancelled = false
    api
      .listSessions()
      .then((rows) => !cancelled && setItems(rows))
      .catch((e: Error) => !cancelled && setError(e.message))
    return () => {
      cancelled = true
    }
  }, [auth.enabled, auth.session])

  return { items, error }
}
