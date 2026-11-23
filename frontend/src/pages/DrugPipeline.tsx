import { ArrowUpRight, Network } from 'lucide-react'
import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { EmptyState, FilterBar, SearchInput, Select } from '@/components/ui/Controls'
import { PageHeader } from '@/components/ui/PageHeader'
import { StatCard, StatGrid } from '@/components/ui/StatCard'
import { useLibrary } from '@/hooks/useLibrary'
import { compoundInfo, mentions, trialInfo, type CompoundInfo } from '@/lib/evidence'
import { cn, plural } from '@/lib/utils'
import type { LibraryRecord } from '@/types/research'

// Columns use ChEMBL's max_phase exactly as recorded. PharmaLens never infers a phase or an approval.
const COLUMNS: { id: string; label: string; note: string; match: (p: number | null) => boolean; tone: string }[] = [
  { id: 'none', label: 'Phase not recorded', note: 'ChEMBL max phase missing or unknown', match: (p) => p === null || p <= 0, tone: 'border-t-slate-300' },
  { id: '1', label: 'Phase 1', note: 'Includes early phase 1', match: (p) => p === 0.5 || p === 1, tone: 'border-t-slate-400' },
  { id: '2', label: 'Phase 2', note: '', match: (p) => p === 2, tone: 'border-t-accent-300' },
  { id: '3', label: 'Phase 3', note: '', match: (p) => p === 3, tone: 'border-t-accent-600' },
  { id: '4', label: 'Approved', note: 'In at least one indication or region', match: (p) => p === 4, tone: 'border-t-ink-900' },
]

interface PipelineItem {
  record: LibraryRecord
  info: CompoundInfo
  trials: LibraryRecord[]
  conditions: string[]
  targets: string[]
  actions: string[]
}

function names(c: CompoundInfo): string[] {
  return [c.name, ...c.synonyms].filter((n) => n.length >= 4)
}

export default function DrugPipeline() {
  const { records, error } = useLibrary()
  const [query, setQuery] = useState('')
  const [condition, setCondition] = useState('all')
  const [target, setTarget] = useState('all')
  const [action, setAction] = useState('all')

  const items = useMemo<PipelineItem[]>(() => {
    const all = records ?? []
    const trials = all.filter((r) => r.category === 'clinical_trial').map((r) => ({ r, info: trialInfo(r) }))
    return all
      .filter((r) => r.category === 'compound' && r.source_name === 'chembl')
      .map((record) => {
        const info = compoundInfo(record)
        const ns = names(info)
        const hit = (text: string) => ns.some((n) => mentions(text, n))
        const linked = trials.filter((t) => t.info.interventions.some(hit) || hit(t.r.title))
        return {
          record,
          info,
          trials: linked.map((t) => t.r),
          conditions: [...new Set(linked.flatMap((t) => t.info.conditions))],
          targets: [...new Set(info.mechanisms.flatMap((m) => (m.targetSymbols.length ? m.targetSymbols : m.targetName ? [m.targetName] : [])))],
          actions: [...new Set(info.mechanisms.map((m) => m.actionType).filter((a): a is string => !!a))],
        }
      })
      .sort((a, b) => b.trials.length - a.trials.length || a.info.name.localeCompare(b.info.name))
  }, [records])

  const options = (values: string[]) => [...new Set(values)].sort((a, b) => a.localeCompare(b))
  const conditionOptions = options(items.flatMap((i) => i.conditions))
  const targetOptions = options(items.flatMap((i) => i.targets))
  const actionOptions = options(items.flatMap((i) => i.actions))

  const filtered = items.filter((i) => {
    const hay = [i.info.name, ...i.info.synonyms, ...i.targets, ...i.info.mechanisms.map((m) => m.mechanism)].join(' ').toLowerCase()
    return (
      (!query || hay.includes(query.toLowerCase())) &&
      (condition === 'all' || i.conditions.includes(condition)) &&
      (target === 'all' || i.targets.includes(target)) &&
      (action === 'all' || i.actions.includes(action))
    )
  })

  return (
    <div className="space-y-6">
      <PageHeader
        crumbs={[{ label: 'Workspace', to: '/' }, { label: 'Drug pipeline' }]}
        title="Drug Pipeline"
        subtitle="Compounds in your research grouped by the highest development phase ChEMBL records for them. Phase applies to any indication, not necessarily the disease you researched."
      />

      <StatGrid>
        <StatCard label="Compounds" value={records ? items.length : '—'} hint="Exact ChEMBL matches" />
        <StatCard label="Approved somewhere" value={records ? items.filter((i) => i.info.maxPhase === 4).length : '—'} hint="ChEMBL max phase 4" />
        <StatCard label="In clinical development" value={records ? items.filter((i) => i.info.maxPhase !== null && i.info.maxPhase > 0 && i.info.maxPhase < 4).length : '—'} hint="Max phase 1–3" />
        <StatCard label="Named in your trials" value={records ? items.filter((i) => i.trials.length).length : '—'} hint="Appear as a trial intervention" />
      </StatGrid>

      <FilterBar>
        <SearchInput value={query} onChange={setQuery} placeholder="Search compound, synonym, target or mechanism…" className="min-w-[16rem] flex-[2]" />
        <Select label="Condition" value={condition} onChange={setCondition} options={[{ value: 'all', label: 'All conditions (from trials)' }, ...conditionOptions.map((c) => ({ value: c, label: c }))]} />
        <Select label="Target" value={target} onChange={setTarget} options={[{ value: 'all', label: 'All targets' }, ...targetOptions.map((t) => ({ value: t, label: t }))]} />
        <Select label="Mechanism" value={action} onChange={setAction} options={[{ value: 'all', label: 'All mechanism types' }, ...actionOptions.map((a) => ({ value: a, label: a.toLowerCase() }))]} />
      </FilterBar>

      {error ? (
        <p className="text-sm text-rose-700">{error}</p>
      ) : !records ? (
        <p className="text-sm text-slate-500">Loading compounds…</p>
      ) : items.length === 0 ? (
        <EmptyState title="No compounds yet">
          The Compound agent looks up drugs named in your question and in retrieved trials.{' '}
          <Link to="/" className="font-medium text-accent-700 hover:underline">
            Start research
          </Link>
        </EmptyState>
      ) : (
        <div className="grid gap-4 overflow-x-auto pb-2 lg:grid-cols-5">
          {COLUMNS.map((col) => {
            const cards = filtered.filter((i) => col.match(i.info.maxPhase))
            return (
              <section key={col.id} className={cn('min-w-[14rem] rounded-lg border border-t-4 border-slate-200 bg-slate-50/60', col.tone)} aria-label={col.label}>
                <header className="px-3 pb-2 pt-3">
                  <p className="flex items-baseline justify-between text-sm font-semibold text-ink-900">
                    {col.label} <span className="text-xs font-normal tabular-nums text-slate-500">{cards.length}</span>
                  </p>
                  {col.note && <p className="text-[11px] text-slate-500">{col.note}</p>}
                </header>
                <ul className="space-y-2 px-3 pb-3">
                  {cards.length === 0 && <li className="py-4 text-center text-xs text-slate-400">None</li>}
                  {cards.map((i) => (
                    <PipelineCard key={i.record.record_id} item={i} />
                  ))}
                </ul>
              </section>
            )
          })}
        </div>
      )}
      <p className="text-xs text-slate-500">
        Source: ChEMBL max phase and mechanisms; linked trials are your retrieved ClinicalTrials.gov records that name the compound. Counts reflect your retrieved records only.
      </p>
    </div>
  )
}

function PipelineCard({ item }: { item: PipelineItem }) {
  const { info, record, trials, targets } = item
  return (
    <li className="rounded-md border border-slate-200 bg-white p-3 text-sm">
      <div className="flex items-start justify-between gap-2">
        <Link to={`/drugs/${info.chemblId}`} className="font-medium capitalize text-ink-900 hover:text-accent-700">
          {info.name.toLowerCase()}
        </Link>
        <a href={record.source_url} target="_blank" rel="noreferrer" aria-label={`${info.chemblId} on ChEMBL`} className="text-accent-600">
          <ArrowUpRight className="h-3.5 w-3.5" aria-hidden="true" />
        </a>
      </div>
      <p className="mt-0.5 text-[11px] text-slate-500">{[info.moleculeType, info.firstApproval ? `first approved ${info.firstApproval}` : null].filter(Boolean).join(' · ')}</p>
      {info.mechanisms[0] && <p className="mt-1.5 line-clamp-2 text-xs text-slate-600">{info.mechanisms[0].mechanism}</p>}
      {targets.length > 0 && (
        <p className="mt-1.5 flex flex-wrap gap-1">
          {targets.slice(0, 4).map((t) => (
            <span key={t} className="rounded bg-accent-50 px-1.5 py-0.5 font-mono text-[10px] text-accent-700">
              {t}
            </span>
          ))}
        </p>
      )}
      <div className="mt-2 flex flex-wrap items-center justify-between gap-2 border-t border-slate-100 pt-2 text-[11px] text-slate-500">
        <span>{trials.length ? plural(trials.length, 'linked trial') : 'No linked trials'}</span>
        <Link to={`/graph?focus=${encodeURIComponent(`compound:${info.chemblId}`)}`} className="inline-flex items-center gap-1 text-accent-700 hover:underline">
          <Network className="h-3 w-3" aria-hidden="true" /> Graph
        </Link>
      </div>
      {(info.withdrawn || info.blackBoxWarning) && (
        <p className="mt-1.5 flex gap-1.5">
          {info.withdrawn && <span className="rounded bg-rose-50 px-1.5 py-0.5 text-[10px] text-rose-700">Withdrawn</span>}
          {info.blackBoxWarning && <span className="rounded bg-amber-50 px-1.5 py-0.5 text-[10px] text-amber-800">Boxed warning</span>}
        </p>
      )}
    </li>
  )
}
