const STEPS = [
  { name: 'Research Planner', detail: 'Structures the question into targets, compounds and search terms' },
  { name: 'Retrieval agents', detail: 'Literature, clinical-trial, compound and target agents run in parallel' },
  { name: 'Evidence Validation', detail: 'Deduplicates by identifier, classifies evidence and flags gaps' },
  { name: 'Research Synthesis', detail: 'Writes a briefing where every claim cites retrieved records' },
]

export function AgentPipeline() {
  return (
    <section aria-labelledby="pipeline-heading">
      <h2 id="pipeline-heading" className="text-sm font-semibold text-ink-900">
        How a research session runs
      </h2>
      <ol className="mt-3 space-y-0 rounded-lg border border-slate-200 bg-white p-4">
        {STEPS.map((step, i) => (
          <li key={step.name} className="relative flex gap-3 pb-4 last:pb-0">
            {i < STEPS.length - 1 && <span className="absolute left-[11px] top-6 h-full w-px bg-slate-200" aria-hidden="true" />}
            <span className="relative flex h-6 w-6 shrink-0 items-center justify-center rounded-full border border-slate-300 bg-white font-mono text-[11px] text-slate-600">
              {i + 1}
            </span>
            <div>
              <p className="text-sm font-medium text-ink-900">{step.name}</p>
              <p className="text-xs leading-relaxed text-slate-500">{step.detail}</p>
            </div>
          </li>
        ))}
      </ol>
    </section>
  )
}
