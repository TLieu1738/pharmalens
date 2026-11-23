export function Logo({ tagline = false }: { tagline?: boolean }) {
  return (
    <div>
      <div className="flex items-center gap-2.5">
        <svg viewBox="0 0 28 28" className="h-7 w-7" aria-hidden="true">
          <rect width="28" height="28" rx="6" className="fill-accent-600" />
          <circle cx="12.5" cy="12.5" r="5.5" fill="none" strokeWidth="2.2" className="stroke-white" />
          <path d="M16.6 16.6 21 21" strokeWidth="2.4" strokeLinecap="round" className="stroke-white" />
        </svg>
        <span className="text-[19px] font-semibold tracking-tight text-ink-900">PharmaLens</span>
      </div>
      {tagline && <p className="mt-2 text-[10px] font-semibold uppercase tracking-[0.12em] text-accent-700">Research intelligence</p>}
    </div>
  )
}
