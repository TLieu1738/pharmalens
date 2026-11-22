import { AlertTriangle, Download } from 'lucide-react'
import { useMemo, useState } from 'react'
import { EvidenceAssessment } from '@/components/evidence/EvidenceAssessment'
import { EvidenceList } from '@/components/evidence/EvidenceList'
import { AgentProgress } from '@/components/research/AgentProgress'
import { PlanSummary } from '@/components/research/PlanSummary'
import { ReportView } from '@/components/research/ReportView'
import { Panel } from '@/components/ui/Panel'
import { Tabs } from '@/components/ui/Tabs'
import { useEvidence } from '@/hooks/useEvidence'
import { downloadText, reportToMarkdown } from '@/lib/exportMarkdown'
import type { EvidenceCategory, SessionDetail } from '@/types/research'

const CATEGORY_TABS: { id: EvidenceCategory; label: string; empty: string; note?: string }[] = [
  { id: 'literature', label: 'Literature', empty: 'No publications were retrieved.', note: 'Abstracts and metadata from PubMed and Europe PMC. Abstracts are summaries, not full papers.' },
  { id: 'clinical_trial', label: 'Clinical trials', empty: 'No registered trials were retrieved.', note: 'Registrations from ClinicalTrials.gov. A registered or completed trial is not evidence that an intervention works.' },
  { id: 'compound', label: 'Compounds', empty: 'No compound records matched exactly in ChEMBL.', note: 'ChEMBL records. "Max phase" is the highest development phase for any indication, not necessarily this one.' },
  { id: 'target', label: 'Targets', empty: 'No disease–target associations were retrieved.', note: 'Open Targets associations summarise aggregated evidence; they do not establish causation or therapeutic validity.' },
]

export default function ResearchResults({ session }: { session: SessionDetail }) {
  const report = session.report!
  const [tab, setTab] = useState('report')
  const { records, error } = useEvidence(session.session_id, true)
  const numbers = useMemo(() => new Map(report.references.map((r) => [r.record_id, r.number])), [report])
  const byCategory = (c: EvidenceCategory) => (records ?? []).filter((r) => r.category === c)
  const unavailable = session.agents.flatMap((a) => a.sources.filter((s) => !s.ok).map((s) => s.source))

  const tabs = [
    { id: 'report', label: 'Report' },
    ...CATEGORY_TABS.map((t) => ({ id: t.id, label: t.label, count: records ? byCategory(t.id).length : undefined })),
    { id: 'assessment', label: 'Evidence assessment' },
    { id: 'run', label: 'Agent run' },
  ]

  return (
    <div className="space-y-5">
      {unavailable.length > 0 && (
        <div className="flex gap-2 rounded-md border border-amber-200 bg-amber-50 px-3 py-2.5 text-sm text-amber-900">
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
          <p>
            Some sources were unavailable during this run ({[...new Set(unavailable)].join(', ')}). The report is based on partial
            evidence.
          </p>
        </div>
      )}

      <div className="flex items-end justify-between gap-4">
        <Tabs items={tabs} active={tab} onChange={setTab} />
        <button
          onClick={() => downloadText(`pharmalens-${session.session_id.slice(0, 8)}.md`, reportToMarkdown(session))}
          className="mb-1 inline-flex shrink-0 items-center gap-1.5 rounded-md border border-slate-200 bg-white px-2.5 py-1.5 text-xs font-medium text-ink-800 hover:border-slate-300"
        >
          <Download className="h-3.5 w-3.5" aria-hidden="true" /> Export Markdown
        </button>
      </div>

      <div role="tabpanel" id={`panel-${tab}`} aria-labelledby={`tab-${tab}`}>
        {tab === 'report' && (
          <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_18rem]">
            <ReportView report={report} numbers={numbers} />
            <aside className="space-y-4 lg:sticky lg:top-20 lg:self-start">
              <Panel title="Research plan">
                {session.research_plan ? <PlanSummary plan={session.research_plan} /> : <p className="text-sm text-slate-500">Unavailable.</p>}
              </Panel>
            </aside>
          </div>
        )}
        {CATEGORY_TABS.map(
          (t) =>
            tab === t.id &&
            (error ? (
              <p key={t.id} className="text-sm text-rose-700">Could not load evidence: {error}</p>
            ) : records ? (
              <EvidenceList key={t.id} records={byCategory(t.id)} citedNumbers={numbers} emptyMessage={t.empty} note={t.note} />
            ) : (
              <p key={t.id} className="text-sm text-slate-500">Loading evidence…</p>
            )),
        )}
        {tab === 'assessment' &&
          (session.evidence_profile ? (
            <EvidenceAssessment profile={session.evidence_profile} integrity={report.integrity} warnings={session.warnings} />
          ) : (
            <p className="text-sm text-slate-500">No evidence profile recorded.</p>
          ))}
        {tab === 'run' && (
          <Panel title="Agent execution log">
            <AgentProgress agents={session.agents} />
          </Panel>
        )}
      </div>
    </div>
  )
}
