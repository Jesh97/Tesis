import { DownloadIcon } from '../../../components/icons'
import { descargarCSV } from '../../../lib/csv'
import type { IncidentePorMes } from '../hooks/useReportes'

export function IncidentsTrendChart({ data }: { data: IncidentePorMes[] }) {
  const maxValue = Math.max(1, ...data.map((d) => d.total))

  function exportar() {
    descargarCSV('evolucion_incidentes.csv', [['Mes', 'Total'], ...data.map((d) => [d.mes, d.total])])
  }

  return (
    <div className="relative rounded-xl border border-slate-200 bg-white p-5">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-semibold text-slate-900">Evolución de Incidentes (Últimos 12 Meses)</h2>
        <button
          onClick={exportar}
          disabled={data.length === 0}
          aria-label="Descargar datos del gráfico (CSV)"
          title="Descargar datos del gráfico (CSV)"
          className="text-slate-400 hover:text-slate-600 disabled:cursor-not-allowed disabled:opacity-40"
        >
          <DownloadIcon className="h-4 w-4" />
        </button>
      </div>

      {data.length === 0 ? (
        <p className="mt-6 flex h-56 items-center justify-center text-sm text-slate-400">
          Sin incidentes registrados en los últimos 12 meses.
        </p>
      ) : (
        <div className="mt-6 flex h-56 items-end gap-3">
          {data.map((d, index) => {
            const isLast = index === data.length - 1
            return (
              <div
                key={d.mes}
                title={`${d.mes}: ${d.total}`}
                style={{ height: `${(d.total / maxValue) * 100}%` }}
                className={`flex-1 rounded-t-sm ${isLast ? 'bg-red-300' : 'bg-slate-300'}`}
              />
            )
          })}
        </div>
      )}
    </div>
  )
}
