import { Printer } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import { useParams } from 'react-router-dom'
import { EvidenceAssessment } from '@/components/evidence/EvidenceAssessment'
import { Logo } from '@/components/layout/Logo'
import { ReportView } from '@/components/research/ReportView'
import { buttonPrimary } from '@/components/ui/styles'
import { formatDate } from '@/lib/labels'
import { api } from '@/services/api'
import type { SessionDetail } from '@/types/research'

/**
 * Print-optimised report. "Save as PDF" in the browser's print dialog produces the PDF export, with
 * clickable reference links and no extra PDF library.
 */
export default function PrintReport() {
  const { sessionId } = useParams()
  const [session, setSession] = useState<SessionDetail | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!sessionId) return
    api
      .getSession(sessionId)
      .then(setSession)
      .catch((e: Error) => setError(e.message))
  }, [sessionId])

  useEffect(() => {
    if (!session?.report) return
    document.title = `PharmaLens report · ${session.research_plan?.disease_area ?? session.session_id.slice(0, 8)}`
    const t = window.setTimeout(() => window.print(), 600)
    return () => window.clearTimeout(t)
  }, [session])

  const numbers = useMemo(() => new Map((session?.report?.references ?? []).map((r) => [r.record_id, r.number])), [session])

  if (error) return <p className="p-10 text-sm text-rose-700">{error}</p>
  if (!session) return <p className="p-10 text-sm text-slate-500">Preparing report…</p>
  if (!session.report) return <p className="p-10 text-sm text-slate-500">This session has no completed report yet.</p>

  return (
    <div className="mx-auto max-w-[820px] bg-white px-10 py-10 print:max-w-none print:px-0 print:py-0">
      <div className="mb-6 flex justify-end print:hidden">
        <button onClick={() => window.print()} className={buttonPrimary}>
          <Printer className="h-4 w-4" aria-hidden="true" /> Print / Save as PDF
        </button>
      </div>
      <header className="border-b-2 border-accent-600 pb-5">
        <div className="flex items-center justify-between">
          <Logo />
          <span className="text-xs text-slate-500">Research briefing</span>
        </div>
        <h1 className="mt-6 text-2xl font-semibold leading-snug text-ink-900">{session.research_plan?.objective || session.research_question}</h1>
        <dl className="mt-4 grid grid-cols-3 gap-4 text-xs">
          <div>
            <dt className="font-semibold uppercase tracking-wide text-slate-500">Generated</dt>
            <dd className="mt-0.5 text-ink-900">{formatDate(session.report.generated_at, true)}</dd>
          </div>
          <div>
            <dt className="font-semibold uppercase tracking-wide text-slate-500">Evidence retrieved</dt>
            <dd className="mt-0.5 text-ink-900">{formatDate(session.created_at, true)}</dd>
          </div>
          <div>
            <dt className="font-semibold uppercase tracking-wide text-slate-500">References</dt>
            <dd className="mt-0.5 text-ink-900">{session.report.references.length} cited records</dd>
          </div>
        </dl>
      </header>

      <main className="mt-8 [&_section]:break-inside-avoid-page">
        <ReportView session={session} numbers={numbers} />
        {session.evidence_profile && (
          <section className="mt-8 break-before-page">
            <h2 className="text-[15px] font-semibold text-ink-900">Evidence profile</h2>
            <div className="mt-3">
              <EvidenceAssessment profile={session.evidence_profile} integrity={session.report.integrity} warnings={session.warnings} />
            </div>
          </section>
        )}
      </main>

      <footer className="mt-10 border-t border-slate-200 pt-4 text-[11px] text-slate-500">
        PharmaLens · AI-assisted research briefing from public sources · Session {session.session_id} · Not for clinical decision-making
      </footer>
    </div>
  )
}
