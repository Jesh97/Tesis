import { Navigate, Route, Routes } from 'react-router-dom'
import { LoginPage } from './features/auth/pages/LoginPage'
import { IncidentsPage } from './features/incidents/pages/IncidentsPage'
import { MonitoringPage } from './features/monitoring/pages/MonitoringPage'
import { NewsPage } from './features/news/pages/NewsPage'
import { ReportsPage } from './features/reports/pages/ReportsPage'

function App() {
  return (
    <Routes>
      <Route path="/" element={<LoginPage />} />
      <Route path="/monitoreo" element={<MonitoringPage />} />
      <Route path="/incidentes" element={<IncidentsPage />} />
      <Route path="/noticias" element={<NewsPage />} />
      <Route path="/reportes" element={<ReportsPage />} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}

export default App
