import type { ReactElement } from 'react'
import { Navigate, Route, Routes } from 'react-router-dom'
import { LoginPage } from './features/auth/pages/LoginPage'
import { IncidentsPage } from './features/incidents/pages/IncidentsPage'
import { MonitoringPage } from './features/monitoring/pages/MonitoringPage'
import { NewsPage } from './features/news/pages/NewsPage'
import { ReportsPage } from './features/reports/pages/ReportsPage'
import { ZonesPage } from './features/zones/pages/ZonesPage'
import { obtenerSesion } from './lib/session'

function RequireAuth({ children }: { children: ReactElement }) {
  return obtenerSesion() ? children : <Navigate to="/" replace />
}

function App() {
  return (
    <Routes>
      <Route path="/" element={<LoginPage />} />
      <Route path="/monitoreo" element={<RequireAuth><MonitoringPage /></RequireAuth>} />
      <Route path="/incidentes" element={<RequireAuth><IncidentsPage /></RequireAuth>} />
      <Route path="/noticias" element={<RequireAuth><NewsPage /></RequireAuth>} />
      <Route path="/reportes" element={<RequireAuth><ReportsPage /></RequireAuth>} />
      <Route path="/zonas" element={<RequireAuth><ZonesPage /></RequireAuth>} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}

export default App
