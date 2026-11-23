import { ChevronDown, LogOut, Menu } from 'lucide-react'
import { useEffect, useRef, useState, type FormEvent } from 'react'
import { NavLink, useNavigate } from 'react-router-dom'
import { SearchInput } from '@/components/ui/Controls'
import { useAuth } from '@/hooks/useAuth'
import { invalidateLibrary } from '@/hooks/useLibrary'
import { cn } from '@/lib/utils'
import { ApiStatusBadge } from './ApiStatusBadge'

const MOBILE_NAV = [
  { to: '/', label: 'Overview' },
  { to: '/research', label: 'Research Workspace' },
  { to: '/evidence', label: 'Evidence Library' },
  { to: '/drugs', label: 'Drug Intelligence' },
  { to: '/trials', label: 'Clinical Trials' },
  { to: '/saved', label: 'Saved Research' },
]

function UserMenu() {
  const auth = useAuth()
  const navigate = useNavigate()
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!open) return
    const close = (e: MouseEvent) => !ref.current?.contains(e.target as Node) && setOpen(false)
    document.addEventListener('mousedown', close)
    return () => document.removeEventListener('mousedown', close)
  }, [open])

  if (!auth.enabled || !auth.session) return null
  const email = auth.email ?? 'Account'
  const signOut = async () => {
    invalidateLibrary()
    await auth.signOut()
    navigate('/login', { replace: true })
  }

  return (
    <div ref={ref} className="relative">
      <button onClick={() => setOpen((o) => !o)} aria-expanded={open} aria-haspopup="menu" className="flex items-center gap-2.5 rounded-md px-2 py-1 hover:bg-slate-50">
        <span className="flex h-8 w-8 items-center justify-center rounded-full bg-accent-100 text-sm font-semibold uppercase text-accent-700" aria-hidden="true">
          {email[0]}
        </span>
        <span className="hidden max-w-[14rem] truncate text-left text-sm font-medium text-ink-900 lg:block">{email}</span>
        <ChevronDown className="h-4 w-4 text-slate-500" aria-hidden="true" />
      </button>
      {open && (
        <div role="menu" className="absolute right-0 z-30 mt-1 w-56 rounded-md border border-slate-200 bg-white py-1 shadow-lg">
          <p className="truncate px-3 py-2 text-xs text-slate-500">Signed in as {email}</p>
          <button role="menuitem" onClick={() => void signOut()} className="flex w-full items-center gap-2 px-3 py-2 text-sm text-ink-900 hover:bg-slate-50">
            <LogOut className="h-4 w-4" aria-hidden="true" /> Sign out
          </button>
        </div>
      )}
    </div>
  )
}

export function TopBar() {
  const navigate = useNavigate()
  const [query, setQuery] = useState('')
  const [mobileOpen, setMobileOpen] = useState(false)

  const submit = (e: FormEvent) => {
    e.preventDefault()
    const q = query.trim()
    navigate(q ? `/evidence?q=${encodeURIComponent(q)}` : '/evidence')
  }

  return (
    <header className="sticky top-0 z-20 border-b border-slate-200 bg-white/95 backdrop-blur">
      <div className="flex h-16 items-center gap-4 px-6 lg:px-8">
        <button className="md:hidden" onClick={() => setMobileOpen((o) => !o)} aria-label="Open navigation">
          <Menu className="h-5 w-5 text-slate-600" />
        </button>
        <form onSubmit={submit} role="search" className="w-full max-w-md">
          <SearchInput value={query} onChange={setQuery} placeholder="Search your evidence: drugs, trials, publications…" />
        </form>
        <div className="ml-auto flex items-center gap-3">
          <ApiStatusBadge />
          <UserMenu />
        </div>
      </div>
      {mobileOpen && (
        <nav className="border-t border-slate-200 px-4 py-2 md:hidden" aria-label="Workspace">
          {MOBILE_NAV.map((n) => (
            <NavLink
              key={n.to}
              to={n.to}
              end={n.to === '/'}
              onClick={() => setMobileOpen(false)}
              className={({ isActive }) => cn('block rounded px-2 py-2 text-sm', isActive ? 'bg-accent-50 text-accent-700' : 'text-slate-600')}
            >
              {n.label}
            </NavLink>
          ))}
        </nav>
      )}
    </header>
  )
}
