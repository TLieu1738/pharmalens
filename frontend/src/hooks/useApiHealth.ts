import { useEffect, useState } from 'react'
import { api } from '@/services/api'
import type { HealthResponse } from '@/types/api'

type HealthState =
  | { kind: 'loading' }
  | { kind: 'online'; data: HealthResponse }
  | { kind: 'offline'; message: string }

/** Poll the backend health endpoint so the UI reflects real API availability. */
export function useApiHealth(intervalMs = 30_000): HealthState {
  const [state, setState] = useState<HealthState>({ kind: 'loading' })

  useEffect(() => {
    let cancelled = false
    const check = async () => {
      try {
        const data = await api.health()
        if (!cancelled) setState({ kind: 'online', data })
      } catch (err) {
        if (!cancelled) setState({ kind: 'offline', message: err instanceof Error ? err.message : 'Unavailable' })
      }
    }
    void check()
    const id = window.setInterval(check, intervalMs)
    return () => {
      cancelled = true
      window.clearInterval(id)
    }
  }, [intervalMs])

  return state
}
