import { AlertTriangle } from 'lucide-react'
import { useMemo, useState } from 'react'
import { EvidenceAssessment } from '@/components/evidence/EvidenceAssessment'
import { EvidenceList } from '@/components/evidence/EvidenceList'
import { AgentProgress } from '@/components/research/AgentProgress'
import { PlanSummary } from '@/components/research/PlanSummary'
import { ReportView } from '@/components/research/ReportView'
import { SupportingSources } from '@/components/research/SupportingSources'
import { Tabs } from '@/components/ui/Tabs'
import { useEvidence } from '@/hooks/useEvidence'
import { cn } from '@/lib/utils'
import type { EvidenceCategory, SessionDetail } from '@/types/research'

const CATEGORIES: { id: EvidenceCategory; label: string; empty: string; note: string }[] = [
  { id: 'literature', label: 'Literature', empty: 'No publications were retrieved.', note: 'Abstracts and metadata from PubMed and Europe PMC. Abstracts are summaries, not full papers.' },
  { id: 'clinical_trial', label: 'Clinical trials', empty: 'No registered trials were retrieved.', note: 'Registrations from ClinicalTrials.gov. A registered or completed trial is not evidence that an intervention works.' },
  { id: 'compound', label: 'Compounds', empty: 'No compound records matched exactly in ChEMBL.', note: 'ChEMBL records. "Max phase" is the highest development phase for any indication, not necessarily this one.' },
  { id: 'target', label: 'Targets', empty: 'No disease–target associations were retrieved.', note: 'Open Targets associations summarise aggregated evidence; they do not establish causation or therapeutic validity.' },
]

export default function ResearchResults({ session }: { session: SessionDetail }) {
  const report = session.report!
  const [tab, setTab] = useState('summary')
  const [category, setCategory] = useState<EvidenceCategory>('literature')
  const { records, error } = useEvidence(session.session_id, true)
  const numbers = useMemo(() => new Map(report.references.map((r) => [r.record_id, r.number])), [report])
  const byCategory = (c: EvidenceCategory) => (records ?? []).filter((r) => r.category === c)
  const unavailable = [...new Set(session.agents.flatMap((a) => a.sources.filter((s) => !s.ok).map((s) => s.source)))]
  const active = CATEGORIES.find((c) => c.id === category)!

  return (
    <div className="space-y-5">
      {unavailable.length > 0 && (
        <div className="flex gap-2 rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
          <p>Some sources were unavailable during this run ({unavailable.join(', ')}). The report is based on partial evidence.</p>
        </div>
      )}

      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_20rem]">
        <section className="min-w-0 rounded-lg border border-slate-200 bg-white">
          <header className="flex items-center justify-between gap-3 px-6 pt-5">
            <h2 className="text-lg font-semibold text-ink-900">Evidence synthesis</h2>
            <span className="rounded bg-amber-50 px-2.5 py-1 text-xs font-medium text-amber-800">AI draft · verify sources</span>
          </header>
          <div className="mt-3 px-6">
            <Tabs
              items={[
                { id: 'summary', label: 'Summary' },
                { id: 'evidence', label: 'Evidence table', count: records?.length },
                { id: 'trail', label: 'Research trail' },
              ]}
              active={tab}
              onChange={setTab}
            />
          </div>
          <div role="tabpanel" id={`panel-${tab}`} aria-labelledby={`tab-${tab}`} className="px-6 py-6">
            {tab === 'summary' && <ReportView report={report} numbers={numbers} />}

            {tab === 'evidence' && (
              <div className="space-y-4">
                <div className="flex flex-wrap gap-2" role="group" aria-label="Evidence category">
                  {CATEGORIES.map((c) => (
                    <button
                      key={c.id}
                      onClick={() => setCategory(c.id)}
                      aria-pressed={category === c.id}
                      className={cn(
                        'rounded-md border px-3 py-1.5 text-[13px] font-medium',
                        category === c.id ? 'border-accent-600 bg-accent-50 text-accent-700' : 'border-slate-200 text-slate-600 hover:border-slate-300',
                      )}
                    >
                      {c.label}
                      <span className="ml-1.5 font-mono text-[11px] text-slate-400">{records ? byCategory(c.id).length : ''}</span>
                    </button>
                  ))}
                </div>
                {error ? (
                  <p className="text-sm text-rose-700">Could not load evidence: {error}</p>
                ) : records ? (
                  <EvidenceList records={byCategory(category)} citedNumbers={numbers} emptyMessage={active.empty} note={active.note} />
                ) : (
                  <p className="text-sm text-slate-500">Loading evidence…</p>
                )}
              </div>
            )}

            {tab === 'trail' && (
              <div className="space-y-8">
                <section>
                  <h3 className="text-sm font-semibold text-ink-900">1 · Research plan</h3>
                  <div className="mt-3">{session.research_plan ? <PlanSummary plan={session.research_plan} /> : <p className="text-sm text-slate-500">Unavailable.</p>}</div>
                </section>
                <section>
                  <h3 className="text-sm font-semibold text-ink-900">2 · Agent execution log</h3>
                  <div className="mt-3">
                    <AgentProgress agents={session.agents} />
                  </div>
                </section>
                <section>
                  <h3 className="text-sm font-semibold text-ink-900">3 · Evidence validation</h3>
                  <div className="mt-3">
                    {session.evidence_profile ? (
                      <EvidenceAssessment profile={session.evidence_profile} integrity={report.integrity} warnings={session.warnings} />
                    ) : (
                      <p className="text-sm text-slate-500">No evidence profile recorded.</p>
                    )}
                  </div>
                </section>
              </div>
            )}
          </div>
          <p className="border-t border-slate-100 px-6 py-3 text-xs text-slate-500">AI-assisted synthesis · Every finding links to a retrieved record · Validate cited sources before use</p>
        </section>

        <aside className="lg:sticky lg:top-24 lg:self-start">
          <SupportingSources references={report.references} records={records} />
        </aside>
      </div>
    </div>
  )
}
