import { NavLink, Outlet } from 'react-router-dom'
import { cn } from '@/lib/utils'
import { AccountMenu } from './AccountMenu'
import { ApiStatusBadge } from './ApiStatusBadge'
import { Logo } from './Logo'

const navItems = [
  { to: '/', label: 'New research', end: true },
  { to: '/saved', label: 'Saved research', end: false },
]

export function AppLayout() {
  return (
    <div className="flex min-h-screen flex-col">
      <header className="sticky top-0 z-10 border-b border-slate-200 bg-white/95 backdrop-blur">
        <div className="mx-auto flex h-14 max-w-6xl items-center gap-8 px-6">
          <NavLink to="/" aria-label="PharmaLens home">
            <Logo />
          </NavLink>
          <nav className="flex items-center gap-1" aria-label="Primary">
            {navItems.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.end}
                className={({ isActive }) =>
                  cn(
                    'rounded-md px-3 py-1.5 text-sm font-medium transition-colors',
                    isActive ? 'bg-slate-100 text-ink-900' : 'text-slate-500 hover:text-ink-900',
                  )
                }
              >
                {item.label}
              </NavLink>
            ))}
          </nav>
          <div className="ml-auto flex items-center gap-3">
            <ApiStatusBadge />
            <AccountMenu />
          </div>
        </div>
      </header>

      <main className="mx-auto w-full max-w-6xl flex-1 px-6 py-8">
        <Outlet />
      </main>

      <footer className="border-t border-slate-200 bg-white">
        <p className="mx-auto max-w-6xl px-6 py-4 text-xs leading-relaxed text-slate-500">
          PharmaLens is a research-support tool. Outputs are informational, may be incomplete, and must be verified by
          qualified researchers. It is not a medical device and does not provide treatment or dosing advice.
        </p>
      </footer>
    </div>
  )
}
