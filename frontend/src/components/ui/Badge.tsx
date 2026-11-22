import type { ReactNode } from 'react'
import { cn } from '@/lib/utils'

const tones = {
  neutral: 'border-slate-200 bg-slate-50 text-slate-600',
  accent: 'border-accent-100 bg-accent-50 text-accent-700',
  navy: 'border-ink-700/15 bg-ink-900/5 text-ink-800',
  warn: 'border-amber-200 bg-amber-50 text-amber-800',
  danger: 'border-rose-200 bg-rose-50 text-rose-700',
  success: 'border-emerald-200 bg-emerald-50 text-emerald-700',
} as const

export type BadgeTone = keyof typeof tones

export function Badge({ tone = 'neutral', children, className }: { tone?: BadgeTone; children: ReactNode; className?: string }) {
  return (
    <span className={cn('inline-flex items-center gap-1 rounded border px-1.5 py-0.5 text-[11px] font-medium leading-4', tones[tone], className)}>
      {children}
    </span>
  )
}
