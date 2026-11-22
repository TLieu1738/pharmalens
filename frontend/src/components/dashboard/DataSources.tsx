import { BookOpen, FlaskConical, Microscope, Stethoscope, Target } from 'lucide-react'

/**
 * Every source listed here is queried live by the backend (verified with backend/scripts/smoke_sources.py).
 * Do not list a source until it is implemented and verified.
 */
const SOURCES = [
  { name: 'PubMed', detail: 'NCBI E-utilities · publications & abstracts', icon: BookOpen },
  { name: 'Europe PMC', detail: 'REST API · literature incl. preprints', icon: Microscope },
  { name: 'ClinicalTrials.gov', detail: 'API v2 · registered studies', icon: Stethoscope },
  { name: 'ChEMBL', detail: 'EMBL-EBI · compounds & mechanisms', icon: FlaskConical },
  { name: 'Open Targets', detail: 'Platform · disease–target associations', icon: Target },
] as const

export function DataSources() {
  return (
    <section aria-labelledby="sources-heading">
      <h2 id="sources-heading" className="text-sm font-semibold text-ink-900">
        Public evidence sources
      </h2>
      <ul className="mt-3 divide-y divide-slate-100 rounded-lg border border-slate-200 bg-white">
        {SOURCES.map(({ name, detail, icon: Icon }) => (
          <li key={name} className="flex items-center gap-3 px-4 py-3">
            <Icon className="h-4 w-4 shrink-0 text-ink-700" aria-hidden="true" />
            <div className="min-w-0 flex-1">
              <p className="text-sm font-medium text-ink-900">{name}</p>
              <p className="truncate text-xs text-slate-500">{detail}</p>
            </div>
            <span className="rounded border border-emerald-200 bg-emerald-50 px-1.5 py-0.5 text-[11px] font-medium text-emerald-700">
              Live API
            </span>
          </li>
        ))}
      </ul>
      <p className="mt-2 text-xs text-slate-500">Queried at request time. Results are limited to top-ranked records per source.</p>
    </section>
  )
}
