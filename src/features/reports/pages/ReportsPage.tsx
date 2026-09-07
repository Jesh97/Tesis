import { DashboardLayout } from '../../../components/layout/DashboardLayout'
import { AlertTriangleIcon, BellIcon, CompassIcon, DownloadIcon, ShipIcon } from '../../../components/icons'
import { descargarCSV } from '../../../lib/csv'
import { IncidentsTrendChart } from '../components/IncidentsTrendChart'
import { InfractionsBreakdown } from '../components/InfractionsBreakdown'
import { StatCard } from '../components/StatCard'
import { TopZones } from '../components/TopZones'
import { useReportes } from '../hooks/useReportes'

const statIcons = [
  { icon: <AlertTriangleIcon className="h-4 w-4 text-amber-600" />, className: 'bg-amber-100' },
  { icon: <ShipIcon className="h-4 w-4 text-sky-600" />, className: 'bg-sky-100' },
  { icon: <BellIcon className="h-4 w-4 text-violet-600" />, className: 'bg-violet-100' },
  { icon: <CompassIcon className="h-4 w-4 text-slate-600" />, className: 'bg-slate-100' },
]

export function ReportsPage() {
  const { resumen, incidentesPorMes, tiposInfraccion, zonasTop, loading, error } = useReportes()

  const statSummaries = resumen
    ? [
        { label: 'Total Incidentes', value: resumen.total_incidentes.toLocaleString('es-PE') },
        { label: 'Embarc. Capturadas', value: resumen.embarcaciones_capturadas.toLocaleString('es-PE') },
        { label: 'Alertas Procesadas', value: resumen.alertas_procesadas.toLocaleString('es-PE') },
        { label: 'Zonas Críticas', value: resumen.zonas_criticas.toLocaleString('es-PE') },
      ]
    : []

  function exportarReporte() {
    const filas: (string | number)[][] = [
      ['Resumen de Reportes', ''],
      ...statSummaries.map((s) => [s.label, s.value]),
      [],
      ['Evolución de Incidentes (Últimos 12 Meses)'],
      ['Mes', 'Total'],
      ...incidentesPorMes.map((m) => [m.mes, m.total]),
      [],
      ['Tipos de Infracciones'],
      ['Tipo', 'Total', 'Porcentaje'],
      ...tiposInfraccion.map((t) => [t.nombre, t.total, `${t.porcentaje ?? 0}%`]),
      [],
      ['Zonas con Mayor Incidencia'],
      ['Ranking', 'Zona', 'Región', 'Total Incidentes'],
      ...zonasTop.map((z) => [z.ranking, z.nombre, z.region, z.total_incidentes]),
    ]
    const fecha = new Date().toISOString().slice(0, 10)
    descargarCSV(`reporte_pesca_ilegal_${fecha}.csv`, filas)
  }

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
            <button
              onClick={exportarReporte}
              disabled={loading || !resumen}
              className="flex items-center gap-2 rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-medium text-slate-700 shadow-sm hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50"
            >
              <DownloadIcon className="h-4 w-4" />
              Exportar Reporte
            </button>
          </div>

          {error && <p className="mt-6 text-sm text-red-600">No se pudieron cargar los reportes: {error}</p>}
          {!error && loading && <p className="mt-6 text-sm text-slate-500">Cargando…</p>}

          {!error && !loading && (
            <>
              <div className="mt-6 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
                {statSummaries.map((stat, index) => (
                  <StatCard
                    key={stat.label}
                    label={stat.label}
                    value={stat.value}
                    icon={statIcons[index].icon}
                    iconClassName={statIcons[index].className}
                  />
                ))}
              </div>

              <div className="mt-6 grid grid-cols-1 gap-6 lg:grid-cols-[1fr_320px]">
                <IncidentsTrendChart data={incidentesPorMes} />
                <InfractionsBreakdown data={tiposInfraccion} />
              </div>

              <div className="mt-6">
                <TopZones data={zonasTop} />
              </div>
            </>
          )}
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
