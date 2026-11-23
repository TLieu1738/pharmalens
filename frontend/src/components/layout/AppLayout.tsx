import { Bookmark, Columns3, FlaskConical, LayoutGrid, Library, ListChecks, Network, Pill } from 'lucide-react'
import { NavLink, Outlet } from 'react-router-dom'
import { useMySessions } from '@/hooks/useMySessions'
import { formatDate } from '@/lib/labels'
import { cn } from '@/lib/utils'
import { Logo } from './Logo'
import { TopBar } from './TopBar'

const NAV = [
  { to: '/', label: 'Overview', icon: LayoutGrid, end: true },
  { to: '/research', label: 'Research Workspace', icon: FlaskConical, end: false },
  { to: '/evidence', label: 'Evidence Library', icon: Library, end: false },
  { to: '/drugs', label: 'Drug Intelligence', icon: Pill, end: false },
  { to: '/pipeline', label: 'Drug Pipeline', icon: Columns3, end: false },
  { to: '/trials', label: 'Clinical Trials', icon: ListChecks, end: false },
  { to: '/graph', label: 'Knowledge Graph', icon: Network, end: false },
  { to: '/saved', label: 'Saved Research', icon: Bookmark, end: false },
]

function Sidebar() {
  const { items } = useMySessions()
  const last = items?.[0]
  return (
    <aside className="sticky top-0 hidden h-screen w-60 shrink-0 flex-col border-r border-slate-200 bg-white md:flex">
      <div className="px-5 pb-5 pt-5">
        <NavLink to="/" aria-label="PharmaLens overview">
          <Logo tagline />
        </NavLink>
      </div>
      <nav aria-label="Workspace" className="flex-1 px-3">
        <p className="px-2 pb-2 text-[10px] font-semibold uppercase tracking-[0.12em] text-slate-500">Workspace</p>
        <ul className="space-y-0.5">
          {NAV.map(({ to, label, icon: Icon, end }) => (
            <li key={to}>
              <NavLink
                to={to}
                end={end}
                className={({ isActive }) =>
                  cn(
                    'flex items-center gap-3 rounded-md px-2.5 py-2 text-sm transition-colors',
                    isActive ? 'bg-accent-50 font-medium text-accent-700' : 'text-slate-600 hover:bg-slate-50 hover:text-ink-900',
                  )
                }
              >
                <Icon className="h-4 w-4 shrink-0" aria-hidden="true" />
                {label}
              </NavLink>
            </li>
          ))}
        </ul>
      </nav>
      <div className="mx-5 border-t border-slate-200 py-4 text-xs">
        <p className="text-[10px] font-semibold uppercase tracking-[0.12em] text-slate-500">Data coverage</p>
        <p className="mt-2 text-slate-500">7 public sources, queried live</p>
        <p className="mt-2 text-slate-500">Last research run</p>
        <p className="mt-0.5 font-medium text-ink-900">{last ? formatDate(last.created_at, true) : '—'}</p>
      </div>
    </aside>
  )
}

export function AppLayout() {
  return (
    <div className="flex min-h-screen">
      <Sidebar />
      <div className="flex min-w-0 flex-1 flex-col">
        <TopBar />
        <main className="mx-auto w-full max-w-[1180px] flex-1 px-6 py-8 lg:px-8">
          <Outlet />
        </main>
        <footer className="mx-auto flex w-full max-w-[1180px] flex-wrap justify-between gap-2 px-6 pb-6 text-xs text-slate-500 lg:px-8">
          <span>Research-support tool · Outputs are informational and must be verified · Not for clinical decision-making</span>
          <span>PharmaLens</span>
        </footer>
      </div>
    </div>
  )
}
