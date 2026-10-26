import type { ReactElement } from 'react'
import { Navigate, Route, Routes } from 'react-router-dom'
import { ErrorBoundary } from './components/ErrorBoundary'
import { AuditLogPage } from './features/audit/pages/AuditLogPage'
import { LoginPage } from './features/auth/pages/LoginPage'
import { IncidentsPage } from './features/incidents/pages/IncidentsPage'
import { MonitoringPage } from './features/monitoring/pages/MonitoringPage'
import { NewsPage } from './features/news/pages/NewsPage'
import { ReportsPage } from './features/reports/pages/ReportsPage'
import { HistoricoPage } from './features/trends/pages/HistoricoPage'
import { TrendsPage } from './features/trends/pages/TrendsPage'
import { ZonesPage } from './features/zones/pages/ZonesPage'
import { obtenerSesion } from './lib/session'

function RequireAuth({ children }: { children: ReactElement }) {
  return obtenerSesion() ? children : <Navigate to="/" replace />
}

// GET /api/auditoria exige rol "administrador" en el backend (ver
// requiere_rol en server/app/auth_dep.py) -- se redirige acá también para no
// mandar a un analista a una pantalla que solo le va a devolver un error.
function RequireAdmin({ children }: { children: ReactElement }) {
  const sesion = obtenerSesion()
  if (!sesion) return <Navigate to="/" replace />
  return sesion.rol === 'administrador' ? children : <Navigate to="/monitoreo" replace />
}

function App() {
  return (
    <ErrorBoundary>
      <Routes>
        <Route path="/" element={<LoginPage />} />
        <Route path="/monitoreo" element={<RequireAuth><MonitoringPage /></RequireAuth>} />
        <Route path="/incidentes" element={<RequireAuth><IncidentsPage /></RequireAuth>} />
        <Route path="/noticias" element={<RequireAuth><NewsPage /></RequireAuth>} />
        <Route path="/reportes" element={<RequireAuth><ReportsPage /></RequireAuth>} />
        <Route path="/historico" element={<RequireAuth><HistoricoPage /></RequireAuth>} />
        <Route path="/tendencias" element={<RequireAuth><TrendsPage /></RequireAuth>} />
        <Route path="/zonas" element={<RequireAuth><ZonesPage /></RequireAuth>} />
        <Route path="/auditoria" element={<RequireAuth><RequireAdmin><AuditLogPage /></RequireAdmin></RequireAuth>} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </ErrorBoundary>
  )
}

export default App
