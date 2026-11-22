import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { AgentPipeline } from '@/components/dashboard/AgentPipeline'
import { DataSources } from '@/components/dashboard/DataSources'
import { ResearchQuestionForm } from '@/components/research/ResearchQuestionForm'
import { SessionList } from '@/components/research/SessionList'
import { useMySessions } from '@/hooks/useMySessions'
import { rememberSession } from '@/lib/recentSessions'
import { api, ApiError } from '@/services/api'

export default function Dashboard() {
  const navigate = useNavigate()
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const recent = (useMySessions().items ?? []).slice(0, 5)

  const start = async (question: string) => {
    setSubmitting(true)
    setError(null)
    try {
      const { session_id, status } = await api.createResearch(question)
      rememberSession({ session_id, research_question: question, created_at: new Date().toISOString(), status })
      navigate(`/research/${session_id}`)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not start research.')
      setSubmitting(false)
    }
  }

  return (
    <div className="space-y-10">
      <section className="max-w-3xl">
        <p className="font-mono text-xs uppercase tracking-[0.14em] text-accent-600">Research intelligence</p>
        <h1 className="mt-2 text-3xl font-semibold tracking-tight text-ink-900">Turn a biomedical question into a source-backed briefing.</h1>
        <p className="mt-3 text-[15px] leading-relaxed text-slate-600">
          Specialist AI agents plan the investigation, retrieve records from public scientific and regulatory databases, validate the
          evidence, and synthesise a report in which every claim links back to its source.
        </p>
      </section>

      <ResearchQuestionForm onSubmit={start} submitting={submitting} error={error} />

      {recent.length > 0 && (
        <section>
          <div className="flex items-baseline justify-between">
            <h2 className="text-sm font-semibold text-ink-900">Your recent research</h2>
            <Link to="/saved" className="text-xs font-medium text-accent-700 hover:underline">
              View all
            </Link>
          </div>
          <div className="mt-3">
            <SessionList items={recent} empty="" />
          </div>
        </section>
      )}

      <div className="grid gap-8 lg:grid-cols-2">
        <AgentPipeline />
        <DataSources />
      </div>
    </div>
  )
}
