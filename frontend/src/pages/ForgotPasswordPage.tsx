import { useState, type FormEvent } from 'react'
import { Link } from 'react-router-dom'
import { AuthShell, FormMessage, inputClass, submitClass } from '@/components/auth/AuthShell'
import { useAuth } from '@/hooks/useAuth'

/** Requests a password-reset email. The same message is shown whether or not the address has an account. */
export default function ForgotPasswordPage() {
  const auth = useAuth()
  const [email, setEmail] = useState('')
  const [busy, setBusy] = useState(false)
  const [sent, setSent] = useState(false)
  const [message, setMessage] = useState<{ tone: 'error' | 'info'; text: string } | null>(null)

  const submit = async (e: FormEvent) => {
    e.preventDefault()
    setBusy(true)
    setMessage(null)
    try {
      await auth.requestPasswordReset(email)
      setSent(true)
      setMessage({ tone: 'info', text: 'If an account exists for that email, a reset link is on its way. Check your inbox and spam folder.' })
    } catch (err) {
      setMessage({ tone: 'error', text: err instanceof Error ? err.message : 'Could not send the reset email. Please try again.' })
    } finally {
      setBusy(false)
    }
  }

  return (
    <AuthShell
      below={
        <Link to="/login" className="font-medium text-accent-700 hover:underline">
          Back to sign in
        </Link>
      }
    >
      <form onSubmit={submit} aria-labelledby="forgot-title">
        <h1 id="forgot-title" className="text-lg font-semibold text-ink-900">
          Reset your password
        </h1>
        <p className="mt-1 text-sm text-slate-500">Enter your account email and we'll send you a link to choose a new password.</p>
        <label className="mt-6 block text-xs font-medium text-slate-600">
          Email
          <input type="email" required autoFocus autoComplete="email" value={email} onChange={(e) => setEmail(e.target.value)} className={inputClass} />
        </label>
        <FormMessage message={message} />
        <button type="submit" disabled={busy || sent} className={submitClass}>
          {busy ? 'Sending…' : sent ? 'Email sent' : 'Send reset link'}
        </button>
      </form>
    </AuthShell>
  )
}
