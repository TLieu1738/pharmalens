import { Route, Routes } from 'react-router-dom'
import { AppLayout } from '@/components/layout/AppLayout'
import Dashboard from '@/pages/Dashboard'
import ResearchSession from '@/pages/ResearchSession'
import SavedResearch from '@/pages/SavedResearch'
import NotFound from '@/pages/NotFound'

export default function App() {
  return (
    <Routes>
      <Route element={<AppLayout />}>
        <Route index element={<Dashboard />} />
        <Route path="research/:sessionId" element={<ResearchSession />} />
        <Route path="saved" element={<SavedResearch />} />
        <Route path="*" element={<NotFound />} />
      </Route>
    </Routes>
  )
}
