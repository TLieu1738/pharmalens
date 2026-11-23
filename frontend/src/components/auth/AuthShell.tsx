import type { ReactNode } from 'react'
import { Logo } from '@/components/layout/Logo'

/** Centred full-page layout shared by the sign-in, sign-up and password pages. */
export function AuthShell({ children, below }: { children: ReactNode; below?: ReactNode }) {
  return (
    <div className="flex min-h-screen flex-col bg-slate-50">
      <main className="flex flex-1 items-center justify-center px-4 py-12">
        <div className="w-full max-w-sm">
          <div className="mb-8 flex justify-center">
            <Logo />
          </div>
          <div className="rounded-lg border border-slate-200 bg-white p-6 shadow-sm">{children}</div>
          {below && <div className="mt-6 text-center text-sm text-slate-500">{below}</div>}
        </div>
      </main>
      <footer className="px-6 py-4 text-center text-xs text-slate-400">
        Research-support tool. Outputs are informational and must be verified by qualified researchers.
      </footer>
    </div>
  )
}

export const inputClass =
  'mt-1 w-full rounded-md border border-slate-200 px-3 py-2 text-sm focus:border-accent-500 focus:outline-none'
export const submitClass =
  'mt-6 w-full rounded-md bg-ink-900 py-2.5 text-sm font-medium text-white hover:bg-ink-800 disabled:bg-slate-300'

export function FormMessage({ message }: { message: { tone: 'error' | 'info'; text: string } | null }) {
  if (!message) return null
  return (
    <p role={message.tone === 'error' ? 'alert' : 'status'} className={`mt-4 text-sm ${message.tone === 'error' ? 'text-rose-700' : 'text-accent-700'}`}>
      {message.text}
    </p>
  )
}
