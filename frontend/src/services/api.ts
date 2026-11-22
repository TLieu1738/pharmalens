import { supabase } from '@/lib/supabase'
import type { HealthResponse, RootResponse } from '@/types/api'
import type { EvidenceRecord, SessionDetail, SessionStatus, SessionSummary } from '@/types/research'

const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000').replace(/\/$/, '')

export class ApiError extends Error {
  readonly status: number

  constructor(message: string, status: number) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

async function authHeader(): Promise<Record<string, string>> {
  if (!supabase) return {}
  const { data } = await supabase.auth.getSession()
  const token = data.session?.access_token
  return token ? { Authorization: `Bearer ${token}` } : {}
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      ...init,
      headers: { 'Content-Type': 'application/json', ...(await authHeader()), ...init?.headers },
    })
  } catch {
    throw new ApiError('Unable to reach the PharmaLens API. It may be starting up — retry in a moment.', 0)
  }
  if (!response.ok) {
    let detail = response.statusText
    try {
      const body = await response.json()
      if (typeof body?.detail === 'string') detail = body.detail
    } catch {
      /* non-JSON error body */
    }
    throw new ApiError(detail || 'Request failed', response.status)
  }
  return (await response.json()) as T
}

export const api = {
  root: () => request<RootResponse>('/'),
  health: () => request<HealthResponse>('/api/health'),
  createResearch: (research_question: string) =>
    request<{ session_id: string; status: SessionStatus }>('/api/research', {
      method: 'POST',
      body: JSON.stringify({ research_question }),
    }),
  getSession: (id: string) => request<SessionDetail>(`/api/sessions/${encodeURIComponent(id)}`),
  getEvidence: (id: string) => request<EvidenceRecord[]>(`/api/sessions/${encodeURIComponent(id)}/evidence`),
  listSessions: () => request<SessionSummary[]>('/api/sessions'),
}
