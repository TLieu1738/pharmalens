import { useCallback, useEffect, useRef, useState } from 'react'
import { updateRecentStatus } from '@/lib/recentSessions'
import { api, ApiError } from '@/services/api'
import { IDLE_STATUSES, type SessionDetail } from '@/types/research'

const POLL_MS = 2000

interface State {
  data: SessionDetail | null
  error: ApiError | null
  loading: boolean
}

/**
 * Poll a session while work is in progress. Progress shown is the backend's real job and agent state.
 * Polling pauses while the session waits for the user (protocol approval) or has finished; call
 * `refresh` after acting on it (approve, cancel) to resume. The job lives on the server, so leaving and
 * reopening the page reconnects to it. Mount with `key={sessionId}` so state resets per session.
 */
export function useResearchSession(sessionId: string | undefined): State & {
  refresh: () => void
  setData: (d: SessionDetail) => void
} {
  const [state, setState] = useState<State>({ data: null, error: null, loading: true })
  const [nonce, setNonce] = useState(0)
  const timer = useRef<number | undefined>(undefined)

  useEffect(() => {
    if (!sessionId) return
    let cancelled = false
    let failures = 0
    const tick = async () => {
      try {
        const data = await api.getSession(sessionId)
        if (cancelled) return
        failures = 0
        setState({ data, error: null, loading: false })
        updateRecentStatus(sessionId, data.status)
        if (!IDLE_STATUSES.includes(data.status)) timer.current = window.setTimeout(tick, POLL_MS)
      } catch (err) {
        if (cancelled) return
        const apiErr = err instanceof ApiError ? err : new ApiError('Unexpected error', 0)
        failures += 1
        // Keep last good data; retry transient errors a few times (e.g. cold starts) before surfacing.
        if (apiErr.status === 0 && failures < 5) {
          timer.current = window.setTimeout(tick, POLL_MS * failures)
          return
        }
        setState((prev) => ({ data: prev.data, error: apiErr, loading: false }))
      }
    }
    void tick()
    return () => {
      cancelled = true
      window.clearTimeout(timer.current)
    }
  }, [sessionId, nonce])

  const refresh = useCallback(() => setNonce((n) => n + 1), [])
  const setData = useCallback((data: SessionDetail) => setState({ data, error: null, loading: false }), [])
  return { ...state, refresh, setData }
}
