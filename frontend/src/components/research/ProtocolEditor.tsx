import { Check, Loader2, Plus, Save, X } from 'lucide-react'
import { useState, type ReactNode } from 'react'
import { buttonPrimary, buttonSecondary } from '@/components/ui/styles'
import { SOURCE_LABELS } from '@/lib/labels'
import { cn } from '@/lib/utils'
import type { ResearchPlan, SourceName } from '@/types/research'

const ALL_SOURCES = Object.keys(SOURCE_LABELS) as SourceName[]
const inputCls = 'w-full rounded-md border border-slate-200 bg-white px-3 py-2 text-sm text-ink-900 focus:border-accent-500 focus:outline-none'

function Section({ title, hint, children }: { title: string; hint?: string; children: ReactNode }) {
  return (
    <section className="border-t border-slate-100 py-5 first:border-0 first:pt-0">
      <h3 className="text-sm font-semibold text-ink-900">{title}</h3>
      {hint && <p className="mt-0.5 text-xs text-slate-500">{hint}</p>}
      <div className="mt-3 space-y-3">{children}</div>
    </section>
  )
}

/** Editable list of sentences (questions, criteria, outputs). */
function ListField({ label, items, onChange, max, placeholder }: { label: string; items: string[]; onChange: (v: string[]) => void; max: number; placeholder: string }) {
  return (
    <fieldset>
      <legend className="mb-1.5 text-xs font-medium text-slate-600">{label}</legend>
      <ul className="space-y-2">
        {items.map((item, i) => (
          <li key={i} className="flex gap-2">
            <input
              aria-label={`${label} ${i + 1}`}
              value={item}
              onChange={(e) => onChange(items.map((x, j) => (j === i ? e.target.value : x)))}
              className={inputCls}
            />
            <button type="button" onClick={() => onChange(items.filter((_, j) => j !== i))} aria-label={`Remove ${label.toLowerCase()} ${i + 1}`} className="rounded-md border border-slate-200 px-2 text-slate-500 hover:text-rose-700">
              <X className="h-4 w-4" />
            </button>
          </li>
        ))}
      </ul>
      {items.length < max && (
        <button type="button" onClick={() => onChange([...items, ''])} className="mt-2 inline-flex items-center gap-1 text-[13px] font-medium text-accent-700 hover:underline">
          <Plus className="h-3.5 w-3.5" /> {placeholder}
        </button>
      )}
    </fieldset>
  )
}

/** Editable set of short search terms shown as removable chips. */
function TermsField({ label, terms, onChange, max }: { label: string; terms: string[]; onChange: (v: string[]) => void; max: number }) {
  const [draft, setDraft] = useState('')
  const add = () => {
    const t = draft.trim()
    if (t && !terms.some((x) => x.toLowerCase() === t.toLowerCase()) && terms.length < max) onChange([...terms, t])
    setDraft('')
  }
  return (
    <div>
      <p className="mb-1.5 text-xs font-medium text-slate-600">{label}</p>
      <div className="flex flex-wrap items-center gap-1.5 rounded-md border border-slate-200 bg-white p-2 focus-within:border-accent-500">
        {terms.map((t) => (
          <span key={t} className="inline-flex items-center gap-1 rounded bg-accent-50 px-2 py-1 text-xs text-accent-700">
            {t}
            <button type="button" onClick={() => onChange(terms.filter((x) => x !== t))} aria-label={`Remove ${t}`}>
              <X className="h-3 w-3" />
            </button>
          </span>
        ))}
        {terms.length < max && (
          <input
            aria-label={`Add to ${label.toLowerCase()}`}
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' || e.key === ',') {
                e.preventDefault()
                add()
              }
            }}
            onBlur={add}
            placeholder="Type and press Enter"
            className="min-w-[10rem] flex-1 border-0 bg-transparent px-1 py-0.5 text-sm focus:outline-none"
          />
        )}
      </div>
    </div>
  )
}

function clean(plan: ResearchPlan): ResearchPlan {
  const list = (v: string[]) => v.map((x) => x.trim()).filter(Boolean)
  return {
    ...plan,
    objective: plan.objective.trim(),
    literature_query: plan.literature_query.trim(),
    key_questions: list(plan.key_questions),
    additional_literature_queries: list(plan.additional_literature_queries),
    inclusion_criteria: list(plan.inclusion_criteria),
    exclusion_criteria: list(plan.exclusion_criteria),
    intended_outputs: list(plan.intended_outputs),
    known_limitations: list(plan.known_limitations),
  }
}

interface Props {
  initial: ResearchPlan
  onSave: (p: ResearchPlan) => Promise<void>
  onApprove: (p: ResearchPlan) => Promise<void>
  onDiscard: () => Promise<void>
}

/** Review, edit and approve the drafted research protocol before any retrieval runs. */
export function ProtocolEditor({ initial, onSave, onApprove, onDiscard }: Props) {
  const [plan, setPlan] = useState<ResearchPlan>(initial)
  const [busy, setBusy] = useState<'save' | 'approve' | 'discard' | null>(null)
  const [message, setMessage] = useState<{ tone: 'error' | 'info'; text: string } | null>(null)
  const set = <K extends keyof ResearchPlan>(key: K, value: ResearchPlan[K]) => setPlan((p) => ({ ...p, [key]: value }))

  const problems = [
    !plan.literature_query.trim() && 'The main literature query is empty.',
    plan.sources.length === 0 && 'Select at least one data source.',
    plan.date_from && plan.date_to && plan.date_from > plan.date_to && 'The start year is after the end year.',
  ].filter(Boolean) as string[]

  const run = async (kind: 'save' | 'approve' | 'discard', fn: () => Promise<void>, ok?: string) => {
    setBusy(kind)
    setMessage(null)
    try {
      await fn()
      if (ok) setMessage({ tone: 'info', text: ok })
    } catch (err) {
      setMessage({ tone: 'error', text: err instanceof Error ? err.message : 'Something went wrong.' })
    } finally {
      setBusy(null)
    }
  }

  const year = (v: string) => (v ? Math.max(1900, Math.min(2100, Number.parseInt(v, 10) || 0)) || null : null)

  return (
    <section className="rounded-lg border border-slate-200 bg-white" aria-labelledby="protocol-title">
      <header className="flex flex-wrap items-start justify-between gap-3 border-b border-slate-100 px-6 py-5">
        <div>
          <h2 id="protocol-title" className="text-lg font-semibold text-ink-900">
            Review the research protocol
          </h2>
          <p className="mt-1 max-w-2xl text-sm text-slate-600">
            The Research Planner drafted this from your question. Nothing has been searched yet: edit anything below, then approve to start
            retrieval. The approved protocol is saved with the session and shown in the final report.
          </p>
        </div>
        <span className="rounded bg-amber-50 px-2.5 py-1 text-xs font-medium text-amber-800">AI draft · awaiting your approval</span>
      </header>

      <div className="px-6 py-5">
        <Section title="Objective and key questions">
          <label className="block">
            <span className="mb-1.5 block text-xs font-medium text-slate-600">Research objective</span>
            <textarea value={plan.objective} onChange={(e) => set('objective', e.target.value)} rows={2} maxLength={1000} className={inputCls} />
          </label>
          <ListField label="Key research questions" items={plan.key_questions} onChange={(v) => set('key_questions', v)} max={8} placeholder="Add a question" />
        </Section>

        <Section title="Scope" hint="Terms used to search the databases. These are search terms, not findings.">
          <label className="block">
            <span className="mb-1.5 block text-xs font-medium text-slate-600">Disease or condition</span>
            <input value={plan.disease_area ?? ''} onChange={(e) => set('disease_area', e.target.value || null)} className={inputCls} />
          </label>
          <div className="grid gap-3 md:grid-cols-2">
            <TermsField label="Biological targets" terms={plan.biological_targets} onChange={(v) => set('biological_targets', v)} max={10} />
            <TermsField label="Gene symbols (Open Targets focus)" terms={plan.target_gene_symbols} onChange={(v) => set('target_gene_symbols', v.map((x) => x.toUpperCase()))} max={10} />
            <TermsField label="Compounds to look up" terms={plan.compounds} onChange={(v) => set('compounds', v)} max={10} />
            <TermsField label="Drug classes and mechanisms (trial search)" terms={plan.clinical_intervention_terms} onChange={(v) => set('clinical_intervention_terms', v)} max={5} />
          </div>
        </Section>

        <Section title="Search strategy">
          <label className="block">
            <span className="mb-1.5 block text-xs font-medium text-slate-600">Main literature query (PubMed and Europe PMC)</span>
            <input value={plan.literature_query} onChange={(e) => set('literature_query', e.target.value)} className={`${inputCls} font-mono text-[13px]`} />
          </label>
          <ListField label="Additional literature queries" items={plan.additional_literature_queries} onChange={(v) => set('additional_literature_queries', v)} max={3} placeholder="Add a query" />
          <label className="block">
            <span className="mb-1.5 block text-xs font-medium text-slate-600">Clinical trial condition (ClinicalTrials.gov)</span>
            <input value={plan.clinical_condition ?? ''} onChange={(e) => set('clinical_condition', e.target.value || null)} className={inputCls} />
          </label>
          <div className="grid gap-3 sm:grid-cols-4">
            <label className="block">
              <span className="mb-1.5 block text-xs font-medium text-slate-600">From year</span>
              <input type="number" min={1900} max={2100} placeholder="Any" value={plan.date_from ?? ''} onChange={(e) => set('date_from', year(e.target.value))} className={inputCls} />
            </label>
            <label className="block">
              <span className="mb-1.5 block text-xs font-medium text-slate-600">To year</span>
              <input type="number" min={1900} max={2100} placeholder="Any" value={plan.date_to ?? ''} onChange={(e) => set('date_to', year(e.target.value))} className={inputCls} />
            </label>
            <label className="block">
              <span className="mb-1.5 block text-xs font-medium text-slate-600">Max records per source</span>
              <input
                type="number"
                min={5}
                max={100}
                value={plan.max_results_per_source}
                onChange={(e) => set('max_results_per_source', Math.max(5, Math.min(100, Number.parseInt(e.target.value, 10) || 5)))}
                className={inputCls}
              />
            </label>
            <label className="flex items-end gap-2 pb-2 text-sm text-ink-900">
              <input type="checkbox" checked={plan.include_preprints} onChange={(e) => set('include_preprints', e.target.checked)} className="h-4 w-4 accent-accent-600" />
              Include preprints
            </label>
          </div>
          <p className="text-xs text-slate-500">
            Dates filter publication year and trial start date. Larger limits retrieve more records but make the report slower to write; every
            source still reports how many matching records exist.
          </p>
        </Section>

        <Section title="Data sources">
          <div className="flex flex-wrap gap-2" role="group" aria-label="Data sources">
            {ALL_SOURCES.map((s) => {
              const on = plan.sources.includes(s)
              return (
                <button
                  key={s}
                  type="button"
                  aria-pressed={on}
                  onClick={() => set('sources', on ? plan.sources.filter((x) => x !== s) : [...plan.sources, s])}
                  className={cn(
                    'inline-flex items-center gap-1.5 rounded-md border px-3 py-1.5 text-[13px] font-medium',
                    on ? 'border-accent-600 bg-accent-50 text-accent-700' : 'border-slate-200 text-slate-500 hover:border-slate-300',
                  )}
                >
                  {on && <Check className="h-3.5 w-3.5" aria-hidden="true" />}
                  {SOURCE_LABELS[s]}
                </button>
              )
            })}
          </div>
        </Section>

        <Section title="Inclusion and exclusion criteria" hint="Given to the synthesis agent, which must not base findings on excluded records; dates and preprints above are applied as hard filters.">
          <div className="grid gap-5 md:grid-cols-2">
            <ListField label="Include" items={plan.inclusion_criteria} onChange={(v) => set('inclusion_criteria', v)} max={10} placeholder="Add a criterion" />
            <ListField label="Exclude" items={plan.exclusion_criteria} onChange={(v) => set('exclusion_criteria', v)} max={10} placeholder="Add a criterion" />
          </div>
        </Section>

        <Section title="Outputs and limitations">
          <div className="grid gap-5 md:grid-cols-2">
            <ListField label="Intended outputs" items={plan.intended_outputs} onChange={(v) => set('intended_outputs', v)} max={10} placeholder="Add an output" />
            <ListField label="Known limitations" items={plan.known_limitations} onChange={(v) => set('known_limitations', v)} max={10} placeholder="Add a limitation" />
          </div>
        </Section>
      </div>

      <footer className="flex flex-wrap items-center gap-3 border-t border-slate-100 px-6 py-4">
        {problems.length > 0 && <p className="w-full text-sm text-rose-700">{problems.join(' ')}</p>}
        {message && (
          <p role={message.tone === 'error' ? 'alert' : 'status'} className={cn('w-full text-sm', message.tone === 'error' ? 'text-rose-700' : 'text-accent-700')}>
            {message.text}
          </p>
        )}
        <button
          type="button"
          disabled={busy !== null || problems.length > 0}
          onClick={() => void run('approve', () => onApprove(clean(plan)))}
          className={buttonPrimary}
        >
          {busy === 'approve' ? <Loader2 className="h-4 w-4 animate-spin" /> : <Check className="h-4 w-4" />} Approve and start research
        </button>
        <button type="button" disabled={busy !== null || problems.length > 0} onClick={() => void run('save', () => onSave(clean(plan)), 'Draft saved.')} className={buttonSecondary}>
          {busy === 'save' ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />} Save draft
        </button>
        <button type="button" disabled={busy !== null} onClick={() => setPlan(initial)} className="text-[13px] font-medium text-slate-500 hover:text-ink-900">
          Reset edits
        </button>
        <button type="button" disabled={busy !== null} onClick={() => void run('discard', onDiscard)} className="ml-auto text-[13px] font-medium text-rose-700 hover:underline">
          Discard this research
        </button>
      </footer>
    </section>
  )
}
