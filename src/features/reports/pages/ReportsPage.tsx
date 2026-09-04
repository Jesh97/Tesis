import { DashboardLayout } from '../../../components/layout/DashboardLayout'
import { AlertTriangleIcon, BellIcon, CompassIcon, DownloadIcon, ShipIcon } from '../../../components/icons'
import { IncidentsTrendChart } from '../components/IncidentsTrendChart'
import { InfractionsBreakdown } from '../components/InfractionsBreakdown'
import { StatCard } from '../components/StatCard'
import { TopZones } from '../components/TopZones'
import { statSummaries } from '../data/mockReports'

const statIcons = [
  { icon: <AlertTriangleIcon className="h-4 w-4 text-amber-600" />, className: 'bg-amber-100' },
  { icon: <ShipIcon className="h-4 w-4 text-sky-600" />, className: 'bg-sky-100' },
  { icon: <BellIcon className="h-4 w-4 text-violet-600" />, className: 'bg-violet-100' },
  { icon: <CompassIcon className="h-4 w-4 text-slate-600" />, className: 'bg-slate-100' },
]

export function ReportsPage() {
  return (
    <DashboardLayout title="Sistema de Detección de Pesca Ilegal" searchPlaceholder="Buscar embarcación...">
      <div className="flex h-full flex-col overflow-y-auto">
        <div className="flex-1 p-6">
          <div className="flex items-start justify-between">
            <div>
              <h1 className="text-2xl font-semibold text-slate-900">Dashboard de Reportes</h1>
              <p className="mt-1 text-sm text-slate-500">
                Resumen estadístico de incidentes y fiscalización marítima.
              </p>
            </div>
            <button className="flex items-center gap-2 rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-medium text-slate-700 shadow-sm hover:bg-slate-50">
              <DownloadIcon className="h-4 w-4" />
              Exportar Reporte
            </button>
          </div>

          <div className="mt-6 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {statSummaries.map((stat, index) => (
              <StatCard
                key={stat.label}
                label={stat.label}
                value={stat.value}
                trend={stat.trend}
                icon={statIcons[index].icon}
                iconClassName={statIcons[index].className}
              />
            ))}
          </div>

          <div className="mt-6 grid grid-cols-1 gap-6 lg:grid-cols-[1fr_320px]">
            <IncidentsTrendChart />
            <InfractionsBreakdown />
          </div>

          <div className="mt-6">
            <TopZones />
          </div>
        </div>

        <footer className="flex flex-col gap-2 border-t border-slate-200 px-6 py-4 text-xs text-slate-400 sm:flex-row sm:items-center sm:justify-between">
          <p>© 2024 Instituto del Mar del Perú - IMARPE. Todos los derechos reservados.</p>
          <div className="flex items-center gap-4">
            <a href="#" className="hover:text-slate-600">
              Privacidad
            </a>
            <a href="#" className="hover:text-slate-600">
              Términos Técnicos
            </a>
            <a href="#" className="hover:text-slate-600">
              Contacto Institucional
            </a>
          </div>
        </footer>
      </div>
    </DashboardLayout>
  )
}
