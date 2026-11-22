export function Logo() {
  return (
    <div className="flex items-center gap-2.5">
      <svg viewBox="0 0 28 28" className="h-7 w-7" aria-hidden="true">
        <rect width="28" height="28" rx="6" className="fill-ink-900" />
        <circle cx="12.5" cy="12.5" r="5.5" fill="none" strokeWidth="2.2" className="stroke-accent-500" />
        <path d="M16.6 16.6 21 21" strokeWidth="2.4" strokeLinecap="round" className="stroke-accent-500" />
        <path d="M10 12.5h5M12.5 10v5" strokeWidth="1.6" strokeLinecap="round" className="stroke-white" />
      </svg>
      <span className="text-[15px] font-semibold tracking-tight text-ink-900">
        Pharma<span className="text-accent-600">Lens</span>
      </span>
    </div>
  )
}
