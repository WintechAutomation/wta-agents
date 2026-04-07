import { Routes, Route, Navigate } from 'react-router-dom'
import Layout from '@/components/Layout'
import OfficePage from '@/pages/OfficePage'
import OverviewPage from '@/pages/OverviewPage'
import DashboardPage from '@/pages/DashboardPage'
import KnowledgePage from '@/pages/KnowledgePage'
import TaskQueuePage from '@/pages/TaskQueuePage'
import CronPage from '@/pages/CronPage'
import CsSessionsPage from '@/pages/CsSessionsPage'
import GlossaryPage from '@/pages/GlossaryPage'
import ManualBuilderPage from '@/pages/ManualBuilderPage'
import WorkspacePage from '@/pages/WorkspacePage'
import CaptioningPage from '@/pages/CaptioningPage'
import VectorSearchPage from '@/pages/VectorSearchPage'
import SkillsPage from '@/pages/SkillsPage'
import SlackRoutingPage from '@/pages/SlackRoutingPage'
import GraphRAGPage from '@/pages/GraphRAGPage'
import HybridSearchPage from '@/pages/HybridSearchPage'

function App() {
  return (
    <Routes>
      <Route path="/" element={<Layout />}>
        <Route index element={<Navigate to="/office" replace />} />
        <Route path="office" element={<OfficePage />} />
        <Route path="dashboard" element={<DashboardPage />} />
        <Route path="overview" element={<OverviewPage />} />
        <Route path="knowledge" element={<KnowledgePage />} />
        <Route path="task-queue" element={<TaskQueuePage />} />
        <Route path="cron" element={<CronPage />} />
        <Route path="cs-sessions" element={<CsSessionsPage />} />
        <Route path="glossary" element={<GlossaryPage />} />
        <Route path="manual-builder" element={<ManualBuilderPage />} />
        <Route path="workspace" element={<WorkspacePage />} />
        <Route path="captioning" element={<CaptioningPage />} />
        <Route path="vector-search" element={<VectorSearchPage />} />
        <Route path="skills" element={<SkillsPage />} />
        <Route path="slack-routing" element={<SlackRoutingPage />} />
        <Route path="graph-rag" element={<GraphRAGPage />} />
        <Route path="hybrid-search" element={<HybridSearchPage />} />
      </Route>
    </Routes>
  )
}

export default App
