import { SOURCE_LABELS, formatDate } from '@/lib/labels'
import type { SessionDetail } from '@/types/research'

export function reportToMarkdown(session: SessionDetail): string {
  const report = session.report
  if (!report) return ''
  const numbers = new Map(report.references.map((r) => [r.record_id, r.number]))
  const cite = (ids: string[]) => {
    const nums = ids.map((id) => numbers.get(id)).filter(Boolean)
    return nums.length ? ` [${nums.join(', ')}]` : ''
  }
  const lines = [
    `# PharmaLens research briefing`,
    '',
    `**Question:** ${report.research_question}`,
    '',
    `_Evidence retrieved ${formatDate(session.created_at, true)}; report generated ${formatDate(report.generated_at, true)} (AI-generated synthesis)._`,
    '',
    `## Research question`,
    '',
    report.research_question,
    '',
  ]
  const plan = session.research_plan
  if (plan) {
    lines.push('## Approved research protocol', '')
    lines.push(session.protocol_approved_at ? `_Approved ${formatDate(session.protocol_approved_at, true)}._` : '_Run with the drafted protocol._', '')
    const item = (label: string, values: (string | null | undefined)[]) => {
      const v = values.filter(Boolean)
      if (v.length) lines.push(`- **${label}:** ${v.join('; ')}`)
    }
    item('Objective', [plan.objective])
    item('Key questions', plan.key_questions ?? [])
    item('Disease / condition', [plan.disease_area])
    item('Literature queries', [plan.literature_query, ...(plan.additional_literature_queries ?? [])])
    item('Sources', plan.sources.map((s) => SOURCE_LABELS[s]))
    item('Date range', [plan.date_from || plan.date_to ? `${plan.date_from ?? 'any'}–${plan.date_to ?? 'present'}` : null])
    item('Max records per source', [String(plan.max_results_per_source ?? '')])
    item('Inclusion criteria', plan.inclusion_criteria ?? [])
    item('Exclusion criteria', plan.exclusion_criteria ?? [])
    item('Known limitations', plan.known_limitations ?? [])
    lines.push('')
  }
  lines.push('## Methodology and scope', '', report.scope, '')
  const outcomes = session.agents.filter((a) => a.agent_name !== 'research_planner').flatMap((a) => a.sources)
  if (outcomes.length) {
    lines.push('| Source | Query | Matching at source | Retrieved |', '| --- | --- | --- | --- |')
    for (const o of outcomes) {
      const name = SOURCE_LABELS[o.source as keyof typeof SOURCE_LABELS] ?? o.source
      lines.push(`| ${name} | ${(o.query ?? '').replace(/\|/g, '/')} | ${o.total_available ?? 'n/r'} | ${o.ok ? o.record_count : 'failed'} |`)
    }
    lines.push('')
  }
  for (const section of report.sections) {
    lines.push(`## ${section.title}`, '')
    if (!section.statements.length) lines.push('_No supported statements._')
    for (const st of section.statements) {
      const tags: Record<string, string> = {
        hypothesis: '**Hypothesis:** ',
        gap: '**Open question:** ',
        interpretation: '**Interpretation:** ',
        clinical_outcome: '**Clinical outcome:** ',
        comparative_analysis: '**Comparison:** ',
      }
      const status = st.validation_status === 'partially_supported' ? ' _(partially supported)_' : st.validation_status === 'not_verified' ? ' _(not verified)_' : ''
      const limits = st.limitations?.length ? ` _Limitations: ${st.limitations.join(' ')}_` : ''
      lines.push(`- ${tags[st.kind] ?? ''}${st.text}${cite(st.citations)}${status}${limits}`)
    }
    lines.push('')
  }
  lines.push('## References', '')
  for (const ref of report.references) {
    lines.push(`${ref.number}. ${ref.title} — ${SOURCE_LABELS[ref.source_name]}${ref.publication_date ? `, ${ref.publication_date}` : ''}. ${ref.source_url}`)
  }
  lines.push('', '---', '', `> ${report.disclaimer}`, '')
  return lines.join('\n')
}

export function downloadText(filename: string, text: string): void {
  const url = URL.createObjectURL(new Blob([text], { type: 'text/markdown;charset=utf-8' }))
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}
