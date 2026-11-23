import { lazy, Suspense } from 'react'
import { Route, Routes } from 'react-router-dom'
import { RequireAuth } from '@/components/auth/RequireAuth'
import { AppLayout } from '@/components/layout/AppLayout'
import AuthPage from '@/pages/AuthPage'
import ClinicalTrials from '@/pages/ClinicalTrials'
import Dashboard from '@/pages/Dashboard'
import DrugIntelligence from '@/pages/DrugIntelligence'
import EvidenceLibrary from '@/pages/EvidenceLibrary'
import ForgotPasswordPage from '@/pages/ForgotPasswordPage'
import NotFound from '@/pages/NotFound'
import PrintReport from '@/pages/PrintReport'
import ResearchSession, { LatestResearch } from '@/pages/ResearchSession'
import ResetPasswordPage from '@/pages/ResetPasswordPage'
import SavedResearch from '@/pages/SavedResearch'
import DrugPipeline from '@/pages/DrugPipeline'

// Loaded on demand: the graph library is large and only this page needs it.
const KnowledgeGraph = lazy(() => import('@/pages/KnowledgeGraph'))

export default function App() {
  return (
    <Routes>
      <Route path="login" element={<AuthPage mode="signin" />} />
      <Route path="signup" element={<AuthPage mode="signup" />} />
      <Route path="forgot-password" element={<ForgotPasswordPage />} />
      <Route path="reset-password" element={<ResetPasswordPage />} />
      <Route element={<RequireAuth />}>
        <Route path="research/:sessionId/print" element={<PrintReport />} />
        <Route element={<AppLayout />}>
          <Route index element={<Dashboard />} />
          <Route path="research" element={<LatestResearch />} />
          <Route path="research/:sessionId" element={<ResearchSession />} />
          <Route path="evidence" element={<EvidenceLibrary />} />
          <Route path="trials" element={<ClinicalTrials />} />
          <Route path="drugs" element={<DrugIntelligence />} />
          <Route path="drugs/:chemblId" element={<DrugIntelligence />} />
          <Route path="pipeline" element={<DrugPipeline />} />
          <Route
            path="graph"
            element={
              <Suspense fallback={<p className="text-sm text-slate-500">Loading graph…</p>}>
                <KnowledgeGraph />
              </Suspense>
            }
          />
          <Route path="saved" element={<SavedResearch />} />
          <Route path="*" element={<NotFound />} />
        </Route>
      </Route>
    </Routes>
  )
}
