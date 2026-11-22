import { LogOut } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '@/hooks/useAuth'

/** Signed-in account email and sign-out. Signing in happens on the /login page. */
export function AccountMenu() {
  const auth = useAuth()
  const navigate = useNavigate()

  if (!auth.enabled || !auth.session) return null

  const signOut = async () => {
    await auth.signOut()
    navigate('/login', { replace: true })
  }

  return (
    <div className="flex items-center gap-2 text-xs text-slate-600">
      <span className="hidden max-w-[12rem] truncate sm:inline">{auth.email}</span>
      <button onClick={() => void signOut()} className="inline-flex items-center gap-1 rounded-md px-2 py-1 font-medium hover:bg-slate-100">
        <LogOut className="h-3.5 w-3.5" aria-hidden="true" /> Sign out
      </button>
    </div>
  )
}
