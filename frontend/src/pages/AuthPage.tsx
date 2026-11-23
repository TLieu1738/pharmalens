import { useState, type FormEvent } from 'react'
import { Link, Navigate, useLocation, useNavigate } from 'react-router-dom'
import { AuthShell, FormMessage, inputClass, submitClass } from '@/components/auth/AuthShell'
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
    <AuthShell
      below={
        <>
          {copy.switchText}{' '}
          <Link to={copy.switchTo} state={location.state} className="font-medium text-accent-700 hover:underline">
            {copy.switchLink}
          </Link>
        </>
      }
    >
      <form onSubmit={submit} aria-labelledby="auth-title">
        <h1 id="auth-title" className="text-lg font-semibold text-ink-900">
          {copy.title}
        </h1>
        <p className="mt-1 text-sm text-slate-500">{copy.subtitle}</p>

        <label className="mt-6 block text-xs font-medium text-slate-600">
          Email
          <input type="email" required autoFocus autoComplete="email" value={email} onChange={(e) => setEmail(e.target.value)} className={inputClass} />
        </label>
        <label className="mt-4 block text-xs font-medium text-slate-600">
          <span className="flex items-baseline justify-between">
            Password
            {mode === 'signin' && (
              <Link to="/forgot-password" className="font-medium text-accent-700 hover:underline">
                Forgot password?
              </Link>
            )}
          </span>
          <input
            type="password"
            required
            minLength={8}
            autoComplete={mode === 'signin' ? 'current-password' : 'new-password'}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className={inputClass}
          />
          {mode === 'signup' && <span className="mt-1 block font-normal text-slate-400">At least 8 characters.</span>}
        </label>

        <FormMessage message={message} />
        <button type="submit" disabled={busy} className={submitClass}>
          {busy ? 'Please wait…' : copy.submit}
        </button>
      </form>
    </AuthShell>
  )
}
