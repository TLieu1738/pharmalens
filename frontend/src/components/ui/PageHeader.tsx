import type { ReactNode } from 'react'
import { Link } from 'react-router-dom'

export interface Crumb {
  label: string
  to?: string
}

export function PageHeader({
  crumbs,
  eyebrow,
  title,
  subtitle,
  actions,
}: {
  crumbs?: Crumb[]
  eyebrow?: ReactNode
  title: ReactNode
  subtitle?: ReactNode
  actions?: ReactNode
}) {
  return (
    <header className="flex flex-wrap items-start justify-between gap-4">
      <div className="min-w-0 max-w-3xl">
        {crumbs && (
          <nav aria-label="Breadcrumb" className="mb-2 text-[11px] font-medium uppercase tracking-[0.08em] text-slate-500">
            {crumbs.map((c, i) => (
              <span key={c.label}>
                {i > 0 && <span className="mx-1.5 text-slate-300">/</span>}
                {c.to ? (
                  <Link to={c.to} className="hover:text-ink-900">
                    {c.label}
                  </Link>
                ) : (
                  c.label
                )}
              </span>
            ))}
          </nav>
        )}
        {eyebrow && <p className="mb-1 text-sm text-slate-500">{eyebrow}</p>}
        <h1 className="text-[28px] font-semibold leading-tight tracking-tight text-ink-900">{title}</h1>
        {subtitle && <p className="mt-2 text-[15px] leading-relaxed text-slate-600">{subtitle}</p>}
      </div>
      {actions && <div className="flex shrink-0 items-center gap-2">{actions}</div>}
    </header>
  )
}
