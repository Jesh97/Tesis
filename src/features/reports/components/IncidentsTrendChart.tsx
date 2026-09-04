import { MoreVerticalIcon } from '../../../components/icons'
import { monthlyIncidents } from '../data/mockReports'

const maxValue = Math.max(...monthlyIncidents)

export function IncidentsTrendChart() {
  return (
    <div className="relative rounded-xl border border-slate-200 bg-white p-5">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-semibold text-slate-900">Evolución de Incidentes (Últimos 12 Meses)</h2>
        <button aria-label="Más opciones" className="text-slate-400 hover:text-slate-600">
          <MoreVerticalIcon className="h-4 w-4" />
        </button>
      </div>

      <div className="mt-6 flex h-56 items-end gap-3">
        {monthlyIncidents.map((value, index) => {
          const isLast = index === monthlyIncidents.length - 1
          return (
            <div
              key={index}
              style={{ height: `${(value / maxValue) * 100}%` }}
              className={`flex-1 rounded-t-sm ${isLast ? 'bg-red-300' : 'bg-slate-300'}`}
            />
          )
        })}
      </div>

      <div className="pointer-events-none absolute inset-0 flex items-center justify-center">
        <span className="rounded-lg bg-white/90 px-4 py-2 text-xs font-medium text-slate-500 shadow-sm">
          Área del Gráfico Interactivo
        </span>
      </div>
    </div>
  )
}
