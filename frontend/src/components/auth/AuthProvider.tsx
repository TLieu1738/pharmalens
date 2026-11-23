import type { Session } from '@supabase/supabase-js'
import { useEffect, useMemo, useState, type ReactNode } from 'react'
import { AuthContext, type AuthState } from '@/hooks/useAuth'
import { supabase } from '@/lib/supabase'

/** Turns Supabase auth errors into messages suitable for users. */
function friendly(message: string): string {
  if (/rate limit/i.test(message)) return 'Too many emails have been sent recently. Please wait a while and try again.'
  if (/invalid login credentials/i.test(message)) return 'Incorrect email or password.'
  return message
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<Session | null>(null)
  const [loading, setLoading] = useState(Boolean(supabase))

  useEffect(() => {
    if (!supabase) return
    void supabase.auth.getSession().then(({ data }) => {
      setSession(data.session)
      setLoading(false)
    })
    const { data } = supabase.auth.onAuthStateChange((_event, next) => setSession(next))
    return () => data.subscription.unsubscribe()
  }, [])

  const value = useMemo<AuthState>(
    () => ({
      enabled: Boolean(supabase),
      loading,
      session,
      email: session?.user.email ?? null,
      async signIn(email, password) {
        if (!supabase) throw new Error('Authentication is not configured.')
        const { error } = await supabase.auth.signInWithPassword({ email, password })
        if (error) throw new Error(friendly(error.message))
      },
      async signUp(email, password) {
        if (!supabase) throw new Error('Authentication is not configured.')
        const { data, error } = await supabase.auth.signUp({ email, password })
        if (error) throw new Error(friendly(error.message))
        return { needsConfirmation: !data.session }
      },
      async signOut() {
        await supabase?.auth.signOut()
      },
      async requestPasswordReset(email) {
        if (!supabase) throw new Error('Authentication is not configured.')
        const { error } = await supabase.auth.resetPasswordForEmail(email, {
          redirectTo: `${window.location.origin}/reset-password`,
        })
        if (error) throw new Error(friendly(error.message))
      },
      async updatePassword(password) {
        if (!supabase) throw new Error('Authentication is not configured.')
        const { error } = await supabase.auth.updateUser({ password })
        if (error) throw new Error(friendly(error.message))
      },
    }),
    [loading, session],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}
