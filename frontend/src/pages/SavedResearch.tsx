import { useEffect, useState } from 'react'
import { SessionList } from '@/components/research/SessionList'
import { useAuth } from '@/hooks/useAuth'
import { loadRecentSessions } from '@/lib/recentSessions'
import { api } from '@/services/api'
import type { SessionSummary } from '@/types/research'

export default function SavedResearch() {
  const auth = useAuth()
  const [account, setAccount] = useState<SessionSummary[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const device = loadRecentSessions()

  useEffect(() => {
    if (!auth.session) return
    api
      .listSessions()
      .then(setAccount)
      .catch((e: Error) => setError(e.message))
  }, [auth.session])

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight text-ink-900">Saved research</h1>
        <p className="mt-1 text-sm text-slate-600">Reopen completed briefings and their evidence.</p>
      </div>

      {auth.enabled && (
        <section>
          <h2 className="text-sm font-semibold text-ink-900">Your account</h2>
          <div className="mt-3">
            {!auth.session ? (
              <p className="rounded-lg border border-dashed border-slate-300 bg-white px-4 py-6 text-center text-sm text-slate-500">
                Sign in to keep research private to your account and access it from any device.
              </p>
            ) : error ? (
              <p className="text-sm text-rose-700">{error}</p>
            ) : account ? (
              <SessionList items={account} empty="No research saved to your account yet." />
            ) : (
              <p className="text-sm text-slate-500">Loading…</p>
            )}
          </div>
        </section>
      )}

      <section>
        <h2 className="text-sm font-semibold text-ink-900">Started on this device</h2>
        <p className="mt-0.5 text-xs text-slate-500">Includes signed-out demo sessions, which are only reachable by link.</p>
        <div className="mt-3">
          <SessionList items={device} empty="No research started in this browser yet." />
        </div>
      </section>
    </div>
  )
}
