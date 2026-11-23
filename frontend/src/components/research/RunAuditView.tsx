import { EvidenceAssessment } from '@/components/evidence/EvidenceAssessment'
import { AgentProgress } from '@/components/research/AgentProgress'
import { DataSourcesTable, ProtocolSummary } from '@/components/research/RunMethodology'
import { formatDate } from '@/lib/labels'
import type { SessionDetail } from '@/types/research'

function Block({ n, title, children }: { n: number; title: string; children: React.ReactNode }) {
  return (
    <section>
      <h3 className="text-sm font-semibold text-ink-900">
        {n} · {title}
      </h3>
      <div className="mt-3">{children}</div>
    </section>
  )
}

function Fact({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div>
      <dt className="text-[11px] font-semibold uppercase tracking-wide text-slate-500">{label}</dt>
      <dd className="mt-0.5 text-sm text-ink-900">{value}</dd>
    </div>
  )
}

/** Reproducibility and evidence audit for one research run. Contains no secrets or prompts. */
export function RunAuditView({ session }: { session: SessionDetail }) {
  const audit = session.run_audit
  const integrity = session.report?.integrity
  const removed = integrity?.removed_statements ?? []
  return (
    <div className="space-y-8">
      <Block n={1} title="Run record">
        <dl className="grid gap-4 sm:grid-cols-3">
          <Fact label="Question submitted" value={formatDate(session.created_at, true)} />
          <Fact label="Protocol approved" value={session.protocol_approved_at ? formatDate(session.protocol_approved_at, true) : '—'} />
          <Fact label="Report generated" value={session.report ? formatDate(session.report.generated_at, true) : '—'} />
          <Fact label="Model" value={audit ? `${audit.model.id} (planner effort ${audit.model.planner_effort}, synthesis ${audit.model.synthesis_effort})` : session.report?.model ?? '—'} />
          <Fact label="Attempts" value={audit ? `${audit.attempts}${audit.attempts > 1 ? ' (resumed after an interruption)' : ''}` : session.attempts || '—'} />
          <Fact label="Session ID" value={<span className="font-mono text-xs">{session.session_id}</span>} />
        </dl>
      </Block>

      <Block n={2} title="Approved protocol">
        {session.research_plan ? <ProtocolSummary plan={session.research_plan} approvedAt={session.protocol_approved_at} /> : <p className="text-sm text-slate-500">No protocol recorded.</p>}
      </Block>

      <Block n={3} title="Searches run">
        <DataSourcesTable session={session} />
      </Block>

      <Block n={4} title="Agent execution log">
        <AgentProgress agents={session.agents} />
      </Block>

      <Block n={5} title="Deduplication">
        {audit ? (
          <>
            <p className="text-sm text-slate-700">
              {audit.deduplication.records_retrieved} records retrieved → {audit.deduplication.unique_records} unique after merging{' '}
              {audit.deduplication.duplicates_merged} duplicates by DOI, PMID, PMCID, NCT and ChEMBL identifiers.
            </p>
            {audit.deduplication.merges.length > 0 && (
              <ul className="mt-2 space-y-1 font-mono text-[12px] text-slate-600">
                {audit.deduplication.merges.slice(0, 25).map((m) => (
                  <li key={m.kept}>
                    {m.kept} ← {m.merged.join(', ')}
                  </li>
                ))}
              </ul>
            )}
          </>
        ) : (
          <p className="text-sm text-slate-500">Not recorded for this run (it predates the audit trail).</p>
        )}
      </Block>

      <Block n={6} title="Evidence validation">
        {session.evidence_profile && session.report ? (
          <EvidenceAssessment profile={session.evidence_profile} integrity={session.report.integrity} warnings={session.warnings} />
        ) : (
          <p className="text-sm text-slate-500">No validation profile recorded.</p>
        )}
      </Block>

      <Block n={7} title="Claim verification">
        {!integrity ? (
          <p className="text-sm text-slate-500">No report was generated.</p>
        ) : (
          <div className="space-y-2 text-sm text-slate-700">
            <p>
              Citations checked against this session's saved evidence; numbers, price, efficacy and approval rules applied in code; support
              check by a separate model call: <strong>{integrity.semantic_check === 'completed' ? 'completed' : integrity.semantic_check === 'unavailable' ? 'unavailable (claims marked “Not verified”)' : 'not run'}</strong>.
            </p>
            {integrity.status_counts && (
              <ul className="flex flex-wrap gap-2">
                {Object.entries(integrity.status_counts).map(([k, v]) => (
                  <li key={k} className="rounded border border-slate-200 px-2 py-1 font-mono text-xs">
                    {k.replace(/_/g, ' ')}: {v}
                  </li>
                ))}
              </ul>
            )}
            {(integrity.relabelled?.length ?? 0) > 0 && (
              <div>
                <p className="mt-2 font-medium text-ink-900">Relabelled as hypotheses</p>
                <ul className="mt-1 space-y-1">
                  {integrity.relabelled!.map((r, i) => (
                    <li key={i} className="text-xs text-slate-600">
                      “{r.text}” — {r.reason}
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        )}
      </Block>

      <Block n={8} title="Claims removed before publication">
        {!integrity ? (
          <p className="text-sm text-slate-500">No report was generated.</p>
        ) : removed.length === 0 ? (
          <p className="text-sm text-slate-600">
            None. All {integrity.findings_with_citations} findings cite records that were actually retrieved
            {integrity.citations_removed_invalid ? `; ${integrity.citations_removed_invalid} invalid citations were dropped from otherwise supported statements` : ''}.
          </p>
        ) : (
          <ul className="space-y-2">
            {removed.map((r, i) => (
              <li key={i} className="rounded-md border border-rose-100 bg-rose-50/50 px-3 py-2 text-sm">
                <p className="text-slate-700 line-through decoration-rose-300">{r.text}</p>
                <p className="mt-0.5 text-xs text-rose-700">
                  {r.section} · {r.status ? `${r.status} · ` : ''}
                  {r.reason}
                  {r.citations?.length ? ` · cited ${r.citations.join(', ')}` : ''}
                </p>
              </li>
            ))}
          </ul>
        )}
        {integrity?.invalid_citations && integrity.invalid_citations.length > 0 && (
          <p className="mt-2 text-xs text-slate-500">Invalid citation IDs dropped: {integrity.invalid_citations.join(', ')}</p>
        )}
      </Block>
    </div>
  )
}
