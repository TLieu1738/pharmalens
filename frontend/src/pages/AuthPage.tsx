import { useState, type FormEvent } from 'react'
import { Link, Navigate, useLocation, useNavigate } from 'react-router-dom'
import { Logo } from '@/components/layout/Logo'
import { useAuth } from '@/hooks/useAuth'

type Mode = 'signin' | 'signup'

const COPY: Record<Mode, { title: string; subtitle: string; submit: string; switchText: string; switchLink: string; switchTo: string }> = {
  signin: {
    title: 'Sign in',
    subtitle: 'Welcome back. Sign in to start research and open your saved briefings.',
    submit: 'Sign in',
    switchText: "Don't have an account?",
    switchLink: 'Create one',
    switchTo: '/signup',
  },
  signup: {
    title: 'Create your account',
    subtitle: 'Your research sessions are private to your account and saved for later.',
    submit: 'Create account',
    switchText: 'Already have an account?',
    switchLink: 'Sign in',
    switchTo: '/login',
  },
}

/** Full-page sign-in / sign-up screen. Signed-in users are sent on to where they were going. */
export default function AuthPage({ mode }: { mode: Mode }) {
  const auth = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const from = (location.state as { from?: string } | null)?.from ?? '/'
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState<{ tone: 'error' | 'info'; text: string } | null>(null)
  const copy = COPY[mode]

  if (!auth.enabled || auth.session) return <Navigate to={from} replace />

  const submit = async (e: FormEvent) => {
    e.preventDefault()
    setBusy(true)
    setMessage(null)
    try {
      if (mode === 'signin') {
        await auth.signIn(email, password)
        navigate(from, { replace: true })
      } else {
        const { needsConfirmation } = await auth.signUp(email, password)
        if (needsConfirmation) {
          setMessage({ tone: 'info', text: 'Account created. Check your email to confirm it, then sign in.' })
        } else {
          navigate(from, { replace: true })
        }
      }
    } catch (err) {
      setMessage({ tone: 'error', text: err instanceof Error ? err.message : 'Something went wrong. Please try again.' })
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="flex min-h-screen flex-col bg-slate-50">
      <main className="flex flex-1 items-center justify-center px-4 py-12">
        <div className="w-full max-w-sm">
          <div className="mb-8 flex justify-center">
            <Logo />
          </div>
          <form onSubmit={submit} className="rounded-lg border border-slate-200 bg-white p-6 shadow-sm" aria-labelledby="auth-title">
            <h1 id="auth-title" className="text-lg font-semibold text-ink-900">
              {copy.title}
            </h1>
            <p className="mt-1 text-sm text-slate-500">{copy.subtitle}</p>

            <label className="mt-6 block text-xs font-medium text-slate-600">
              Email
              <input
                type="email"
                required
                autoFocus
                autoComplete="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="mt-1 w-full rounded-md border border-slate-200 px-3 py-2 text-sm focus:border-accent-500 focus:outline-none"
              />
            </label>
            <label className="mt-4 block text-xs font-medium text-slate-600">
              Password
              <input
                type="password"
                required
                minLength={8}
                autoComplete={mode === 'signin' ? 'current-password' : 'new-password'}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="mt-1 w-full rounded-md border border-slate-200 px-3 py-2 text-sm focus:border-accent-500 focus:outline-none"
              />
              {mode === 'signup' && <span className="mt-1 block font-normal text-slate-400">At least 8 characters.</span>}
            </label>

            {message && (
              <p role={message.tone === 'error' ? 'alert' : 'status'} className={`mt-4 text-sm ${message.tone === 'error' ? 'text-rose-700' : 'text-accent-700'}`}>
                {message.text}
              </p>
            )}

            <button
              type="submit"
              disabled={busy}
              className="mt-6 w-full rounded-md bg-ink-900 py-2.5 text-sm font-medium text-white hover:bg-ink-800 disabled:bg-slate-300"
            >
              {busy ? 'Please wait…' : copy.submit}
            </button>
          </form>

          <p className="mt-6 text-center text-sm text-slate-500">
            {copy.switchText}{' '}
            <Link to={copy.switchTo} state={location.state} className="font-medium text-accent-700 hover:underline">
              {copy.switchLink}
            </Link>
          </p>
        </div>
      </main>
      <footer className="px-6 py-4 text-center text-xs text-slate-400">
        Research-support tool. Outputs are informational and must be verified by qualified researchers.
      </footer>
    </div>
  )
}
