import { useRef, type KeyboardEvent } from 'react'
import { cn } from '@/lib/utils'

export interface TabItem {
  id: string
  label: string
  count?: number
}

/** Accessible tab list (WAI-ARIA tabs pattern with arrow-key navigation). */
export function Tabs({ items, active, onChange }: { items: TabItem[]; active: string; onChange: (id: string) => void }) {
  const refs = useRef<Record<string, HTMLButtonElement | null>>({})
  const onKey = (e: KeyboardEvent, index: number) => {
    if (e.key !== 'ArrowRight' && e.key !== 'ArrowLeft') return
    e.preventDefault()
    const next = items[(index + (e.key === 'ArrowRight' ? 1 : -1) + items.length) % items.length]
    onChange(next.id)
    refs.current[next.id]?.focus()
  }
  return (
    <div role="tablist" className="flex gap-1 overflow-x-auto border-b border-slate-200">
      {items.map((item, i) => {
        const selected = item.id === active
        return (
          <button
            key={item.id}
            ref={(el) => {
              refs.current[item.id] = el
            }}
            role="tab"
            id={`tab-${item.id}`}
            aria-selected={selected}
            aria-controls={`panel-${item.id}`}
            tabIndex={selected ? 0 : -1}
            onClick={() => onChange(item.id)}
            onKeyDown={(e) => onKey(e, i)}
            className={cn(
              '-mb-px whitespace-nowrap border-b-2 px-3 py-2 text-sm font-medium transition-colors',
              selected ? 'border-accent-600 text-ink-900' : 'border-transparent text-slate-500 hover:text-ink-900',
            )}
          >
            {item.label}
            {item.count != null && <span className="ml-1.5 font-mono text-[11px] text-slate-400">{item.count}</span>}
          </button>
        )
      })}
    </div>
  )
}
