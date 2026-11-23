import { ExternalLink } from 'lucide-react'
import { Badge } from '@/components/ui/Badge'
import { EVIDENCE_TYPE_LABELS, SOURCE_LABELS, formatDate } from '@/lib/labels'
import { DataSourcesTable, Methodology, ProtocolSummary } from '@/components/research/RunMethodology'
import type { SessionDetail, Statement } from '@/types/research'

function Citations({ ids, numbers }: { ids: string[]; numbers: Map<string, number> }) {
  if (!ids.length) return null
  const nums = ids.map((id) => numbers.get(id)).filter((n): n is number => n != null).sort((a, b) => a - b)
  return (
    <sup className="ml-0.5 whitespace-nowrap">
      [
      {nums.map((n, i) => (
        <span key={n}>
          <a href={`#ref-${n}`} className="font-medium text-accent-700 hover:underline" aria-label={`Reference ${n}`}>
            {n}
          </a>
          {i < nums.length - 1 && ','}
        </span>
      ))}
      ]
    </sup>
  )
}

function StatementItem({ st, numbers }: { st: Statement; numbers: Map<string, number> }) {
  return (
    <li className="flex gap-2 text-[14px] leading-relaxed text-slate-800">
      <span className="mt-[9px] h-1 w-1 shrink-0 rounded-full bg-slate-400" aria-hidden="true" />
      <p>
        {st.kind === 'hypothesis' && (
          <Badge tone="warn" className="mr-1.5 align-[1px]">
            Hypothesis
          </Badge>
        )}
        {st.kind === 'gap' && (
          <Badge tone="navy" className="mr-1.5 align-[1px]">
            Open question
          </Badge>
        )}
        {st.text}
        <Citations ids={st.citations} numbers={numbers} />
      </p>
    </li>
  )
}

function SectionHeading({ children }: { children: React.ReactNode }) {
  return <h2 className="text-[15px] font-semibold text-ink-900">{children}</h2>
}

/**
 * The research report. AI-written sections come from `report.sections` (each finding already checked against
 * retrieved records); the question, protocol, methodology and data-source sections are built from the
 * session record by code.
 */
export function ReportView({ session, numbers }: { session: SessionDetail; numbers: Map<string, number> }) {
  const report = session.report!
  const [summary, ...rest] = report.sections
  const shown = rest.filter((s) => s.statements.length > 0)
  const empty = rest.filter((s) => s.statements.length === 0)
  return (
    <div className="space-y-7">
      {summary && (
        <section className="rounded-lg bg-accent-50 p-5">
          <h2 className="text-[13px] font-semibold text-accent-700">{summary.title}</h2>
          <ul className="mt-3 space-y-2">
            {summary.statements.map((st, i) => (
              <StatementItem key={i} st={st} numbers={numbers} />
            ))}
          </ul>
        </section>
      )}

      <section>
        <SectionHeading>Research question</SectionHeading>
        <p className="mt-1.5 text-[14px] leading-relaxed text-slate-700">{report.research_question}</p>
      </section>

      {session.research_plan && (
        <section>
          <SectionHeading>Approved research protocol</SectionHeading>
          <div className="mt-1.5">
            <ProtocolSummary plan={session.research_plan} approvedAt={session.protocol_approved_at} />
          </div>
        </section>
      )}

      <section>
        <SectionHeading>Methodology</SectionHeading>
        <div className="mt-1.5">
          <Methodology session={session} />
        </div>
      </section>

      <section>
        <SectionHeading>Data sources</SectionHeading>
        <div className="mt-2">
          <DataSourcesTable session={session} />
        </div>
      </section>

      {shown.map((section) => (
        <section key={section.key}>
          <SectionHeading>{section.title}</SectionHeading>
          <ul className="mt-2 space-y-2">
            {section.statements.map((st, i) => (
              <StatementItem key={i} st={st} numbers={numbers} />
            ))}
          </ul>
        </section>
      ))}

      {empty.length > 0 && (
        <p className="text-xs text-slate-500">
          No evidence-supported statements for: {empty.map((s) => s.title.toLowerCase()).join('; ')}. These sections are omitted rather than
          filled without evidence.
        </p>
      )}

      <section aria-labelledby="refs">
        <h2 id="refs" className="text-[15px] font-semibold text-ink-900">
          References
        </h2>
        <ol className="mt-2 space-y-1.5">
          {report.references.map((ref) => (
            <li key={ref.record_id} id={`ref-${ref.number}`} className="scroll-mt-20 rounded px-1 text-[13px] leading-snug target:bg-accent-50">
              <span className="mr-1.5 font-mono text-slate-400">[{ref.number}]</span>
              <a href={ref.source_url} target="_blank" rel="noreferrer" className="text-ink-900 hover:text-accent-700 hover:underline">
                {ref.title}
                <ExternalLink className="ml-1 inline h-3 w-3 text-slate-400" aria-hidden="true" />
              </a>
              <span className="text-slate-500">
                {' '}
                — {SOURCE_LABELS[ref.source_name]}, {EVIDENCE_TYPE_LABELS[ref.evidence_type].toLowerCase()}
                {ref.evidence_type === 'preprint' ? ' (not peer reviewed)' : ''}
                {ref.publication_date ? `, ${ref.publication_date}` : ''}. Retrieved {formatDate(ref.retrieved_at)}.
              </span>
            </li>
          ))}
        </ol>
      </section>

      <p className="rounded-md border border-amber-200 bg-amber-50 px-3 py-2.5 text-xs leading-relaxed text-amber-900">{report.disclaimer}</p>
    </div>
  )
}
