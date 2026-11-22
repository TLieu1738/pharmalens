import { SessionList } from '@/components/research/SessionList'
import { useMySessions } from '@/hooks/useMySessions'

export default function SavedResearch() {
  const { items, error } = useMySessions()

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight text-ink-900">Saved research</h1>
        <p className="mt-1 text-sm text-slate-600">Reopen completed briefings and their evidence.</p>
      </div>

      <section>
        {error ? (
          <p className="text-sm text-rose-700">{error}</p>
        ) : items ? (
          <SessionList items={items} empty="No research saved yet. Start a question from New research." />
        ) : (
          <p className="text-sm text-slate-500">Loading…</p>
        )}
      </section>
    </div>
  )
}
