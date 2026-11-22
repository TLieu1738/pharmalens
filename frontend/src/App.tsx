import { Route, Routes } from 'react-router-dom'
import { RequireAuth } from '@/components/auth/RequireAuth'
import { AppLayout } from '@/components/layout/AppLayout'
import AuthPage from '@/pages/AuthPage'
import Dashboard from '@/pages/Dashboard'
import ResearchSession from '@/pages/ResearchSession'
import SavedResearch from '@/pages/SavedResearch'
import NotFound from '@/pages/NotFound'

export default function App() {
  return (
    <Routes>
      <Route path="login" element={<AuthPage mode="signin" />} />
      <Route path="signup" element={<AuthPage mode="signup" />} />
      <Route element={<RequireAuth />}>
        <Route element={<AppLayout />}>
          <Route index element={<Dashboard />} />
          <Route path="research/:sessionId" element={<ResearchSession />} />
          <Route path="saved" element={<SavedResearch />} />
          <Route path="*" element={<NotFound />} />
        </Route>
      </Route>
    </Routes>
  )
}
