import { LogIn, LogOut, X } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { useAuth } from '@/hooks/useAuth'

export function AccountMenu() {
  const auth = useAuth()
  const [open, setOpen] = useState(false)
  const [mode, setMode] = useState<'signin' | 'signup'>('signin')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState<{ tone: 'error' | 'info'; text: string } | null>(null)

  if (!auth.enabled || auth.loading) return null

  if (auth.session) {
    return (
      <div className="flex items-center gap-2 text-xs text-slate-600">
        <span className="hidden max-w-[12rem] truncate sm:inline">{auth.email}</span>
        <button onClick={() => void auth.signOut()} className="inline-flex items-center gap-1 rounded-md px-2 py-1 font-medium hover:bg-slate-100" aria-label="Sign out">
          <LogOut className="h-3.5 w-3.5" aria-hidden="true" /> Sign out
        </button>
      </div>
    )
  }

  const submit = async (e: FormEvent) => {
    e.preventDefault()
    setBusy(true)
    setMessage(null)
    try {
      if (mode === 'signin') {
        await auth.signIn(email, password)
        setOpen(false)
      } else {
        const { needsConfirmation } = await auth.signUp(email, password)
        if (needsConfirmation) setMessage({ tone: 'info', text: 'Check your email to confirm your account, then sign in.' })
        else setOpen(false)
      }
    } catch (err) {
      setMessage({ tone: 'error', text: err instanceof Error ? err.message : 'Sign-in failed' })
    } finally {
      setBusy(false)
    }
  }

  return (
    <>
      <button onClick={() => setOpen(true)} className="inline-flex items-center gap-1 rounded-md px-2 py-1 text-xs font-medium text-slate-600 hover:bg-slate-100">
        <LogIn className="h-3.5 w-3.5" aria-hidden="true" /> Sign in
      </button>
      {open && (
        <div className="fixed inset-0 z-30 flex items-start justify-center bg-ink-950/30 px-4 pt-24" onClick={() => setOpen(false)}>
          <form
            onSubmit={submit}
            onClick={(e) => e.stopPropagation()}
            role="dialog"
            aria-modal="true"
            aria-labelledby="auth-title"
            className="w-full max-w-sm rounded-lg border border-slate-200 bg-white p-5 shadow-lg"
          >
            <div className="flex items-center justify-between">
              <h2 id="auth-title" className="text-base font-semibold text-ink-900">
                {mode === 'signin' ? 'Sign in to PharmaLens' : 'Create an account'}
              </h2>
              <button type="button" onClick={() => setOpen(false)} aria-label="Close" className="text-slate-400 hover:text-slate-600">
                <X className="h-4 w-4" />
              </button>
            </div>
            <p className="mt-1 text-xs text-slate-500">Signed-in research is private to your account and listed under Saved research.</p>
            <label className="mt-4 block text-xs font-medium text-slate-600">
              Email
              <input type="email" required autoFocus value={email} onChange={(e) => setEmail(e.target.value)} className="mt-1 w-full rounded-md border border-slate-200 px-3 py-2 text-sm focus:border-accent-500 focus:outline-none" />
            </label>
            <label className="mt-3 block text-xs font-medium text-slate-600">
              Password
              <input type="password" required minLength={8} value={password} onChange={(e) => setPassword(e.target.value)} className="mt-1 w-full rounded-md border border-slate-200 px-3 py-2 text-sm focus:border-accent-500 focus:outline-none" />
            </label>
            {message && <p className={`mt-3 text-xs ${message.tone === 'error' ? 'text-rose-700' : 'text-accent-700'}`}>{message.text}</p>}
            <button type="submit" disabled={busy} className="mt-4 w-full rounded-md bg-ink-900 py-2 text-sm font-medium text-white hover:bg-ink-800 disabled:bg-slate-300">
              {busy ? 'Please wait…' : mode === 'signin' ? 'Sign in' : 'Create account'}
            </button>
            <button type="button" onClick={() => setMode(mode === 'signin' ? 'signup' : 'signin')} className="mt-3 w-full text-xs font-medium text-accent-700 hover:underline">
              {mode === 'signin' ? 'New here? Create an account' : 'Have an account? Sign in'}
            </button>
          </form>
        </div>
      )}
    </>
  )
}
