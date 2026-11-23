import { useState, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { AuthShell, FormMessage, inputClass, submitClass } from '@/components/auth/AuthShell'
import { useAuth } from '@/hooks/useAuth'

/**
 * Landing page for the emailed reset link. Supabase reads the recovery token from the URL and signs the
 * user in temporarily; they then choose a new password here.
 */
export default function ResetPasswordPage() {
  const auth = useAuth()
  const navigate = useNavigate()
  const [password, setPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState<{ tone: 'error' | 'info'; text: string } | null>(null)

  if (auth.loading) return <AuthShell>Checking your reset link…</AuthShell>

  if (!auth.session) {
    return (
      <AuthShell>
        <h1 className="text-lg font-semibold text-ink-900">Reset link expired</h1>
        <p className="mt-1 text-sm text-slate-500">This link is invalid or has already been used. Request a new one to reset your password.</p>
        <Link to="/forgot-password" className={`${submitClass} block text-center`}>
          Request a new link
        </Link>
      </AuthShell>
    )
  }

  const submit = async (e: FormEvent) => {
    e.preventDefault()
    if (password !== confirm) {
      setMessage({ tone: 'error', text: 'The two passwords do not match.' })
      return
    }
    setBusy(true)
    setMessage(null)
    try {
      await auth.updatePassword(password)
      navigate('/', { replace: true })
    } catch (err) {
      setMessage({ tone: 'error', text: err instanceof Error ? err.message : 'Could not update your password.' })
      setBusy(false)
    }
  }

  return (
    <AuthShell>
      <form onSubmit={submit} aria-labelledby="reset-title">
        <h1 id="reset-title" className="text-lg font-semibold text-ink-900">
          Choose a new password
        </h1>
        <p className="mt-1 text-sm text-slate-500">For {auth.email}</p>
        <label className="mt-6 block text-xs font-medium text-slate-600">
          New password
          <input type="password" required minLength={8} autoFocus autoComplete="new-password" value={password} onChange={(e) => setPassword(e.target.value)} className={inputClass} />
          <span className="mt-1 block font-normal text-slate-400">At least 8 characters.</span>
        </label>
        <label className="mt-4 block text-xs font-medium text-slate-600">
          Confirm new password
          <input type="password" required minLength={8} autoComplete="new-password" value={confirm} onChange={(e) => setConfirm(e.target.value)} className={inputClass} />
        </label>
        <FormMessage message={message} />
        <button type="submit" disabled={busy} className={submitClass}>
          {busy ? 'Saving…' : 'Update password'}
        </button>
      </form>
    </AuthShell>
  )
}
