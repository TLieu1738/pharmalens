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
    `## Research question and scope`,
    '',
    report.scope,
    '',
  ]
  for (const section of report.sections) {
    lines.push(`## ${section.title}`, '')
    if (!section.statements.length) lines.push('_No supported statements._')
    for (const st of section.statements) {
      const tag = st.kind === 'hypothesis' ? '**Hypothesis:** ' : st.kind === 'gap' ? '**Open question:** ' : ''
      lines.push(`- ${tag}${st.text}${cite(st.citations)}`)
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
