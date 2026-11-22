import { Navigate, Outlet, useLocation } from 'react-router-dom'
import { useAuth } from '@/hooks/useAuth'

/**
 * Sends signed-out visitors to the sign-in page, remembering where they were going.
 * When Supabase isn't configured (local dev without auth), the app stays open.
 */
export function RequireAuth() {
  const auth = useAuth()
  const location = useLocation()

  if (!auth.enabled) return <Outlet />
  if (auth.loading) return <div className="min-h-screen bg-slate-50" aria-busy="true" />
  if (!auth.session) {
    return <Navigate to="/login" replace state={{ from: location.pathname + location.search }} />
  }
  return <Outlet />
}
