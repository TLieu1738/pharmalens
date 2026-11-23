// Shared Tailwind class strings for buttons and tables.

export const buttonPrimary =
  'inline-flex items-center justify-center gap-1.5 rounded-md bg-accent-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-accent-700 disabled:cursor-not-allowed disabled:bg-slate-300'
export const buttonSecondary =
  'inline-flex items-center justify-center gap-1.5 rounded-md border border-slate-200 bg-white px-4 py-2 text-sm font-medium text-ink-900 transition-colors hover:border-slate-300 hover:bg-slate-50'

/** Table styles shared by the list pages. */
export const table = {
  wrap: 'overflow-x-auto rounded-lg border border-slate-200 bg-white',
  table: 'w-full text-left text-sm',
  head: 'border-b border-slate-200 bg-slate-50 text-[11px] font-semibold uppercase tracking-[0.06em] text-slate-500',
  th: 'px-5 py-3 font-semibold',
  row: 'border-b border-slate-100 last:border-0 hover:bg-slate-50/60',
  td: 'px-5 py-3.5 align-top',
}
