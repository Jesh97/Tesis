import { DownloadIcon } from '../../../components/icons'
import { descargarCSV } from '../../../lib/csv'
import type { IncidentePorMes } from '../hooks/useReportes'

const NOMBRES_MES = ['ene', 'feb', 'mar', 'abr', 'may', 'jun', 'jul', 'ago', 'sep', 'oct', 'nov', 'dic']

/** El backend (vw_incidentes_por_mes) solo devuelve filas para meses que
 * tienen al menos un incidente -- si los 40 incidentes de la demo cayeron
 * todos en el mes actual, "data" traía una sola fila, y el gráfico dibujaba
 * UNA barra ocupando todo el ancho (el bloque sólido que se veía en el
 * dashboard), pese a titularse "Últimos 12 Meses". Acá se completan los 12
 * meses siempre, con 0 en los que no vinieron, para que el eje de tiempo se
 * vea real sin importar cómo esté distribuida la data. */
function completarUltimos12Meses(data: IncidentePorMes[]): { mes: string; total: number; label: string }[] {
  const porMes = new Map(data.map((d) => [d.mes.slice(0, 7), d.total]))
  const hoy = new Date()
  const meses: { mes: string; total: number; label: string }[] = []
  for (let i = 11; i >= 0; i--) {
    const d = new Date(hoy.getFullYear(), hoy.getMonth() - i, 1)
    const clave = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`
    meses.push({ mes: clave, total: porMes.get(clave) ?? 0, label: NOMBRES_MES[d.getMonth()] })
  }
  return meses
}

export function IncidentsTrendChart({ data }: { data: IncidentePorMes[] }) {
  const meses = completarUltimos12Meses(data)
  const maxValue = Math.max(1, ...meses.map((m) => m.total))
  const sinDatos = data.length === 0

  function exportar() {
    descargarCSV('evolucion_incidentes.csv', [['Mes', 'Total'], ...meses.map((m) => [m.mes, m.total])])
  }

  return (
    <div className="relative rounded-xl border border-slate-200 bg-white p-5">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-semibold text-slate-900">Evolución de Incidentes (Últimos 12 Meses)</h2>
        <button
          onClick={exportar}
          disabled={sinDatos}
          aria-label="Descargar datos del gráfico (CSV)"
          title="Descargar datos del gráfico (CSV)"
          className="text-slate-400 hover:text-slate-600 disabled:cursor-not-allowed disabled:opacity-40"
        >
          <DownloadIcon className="h-4 w-4" />
        </button>
      </div>

      {sinDatos ? (
        <p className="mt-6 flex h-56 items-center justify-center text-sm text-slate-400">
          Sin incidentes registrados en los últimos 12 meses.
        </p>
      ) : (
        <div className="mt-6">
          {/* Referencia de escala: sin esto no hay forma de saber si una barra
              representa 2 incidentes o 200 -- solo se ve "más alta que las demás". */}
          <p className="text-[11px] text-slate-400">Máximo: {maxValue.toLocaleString('es-PE')} en un mes</p>
          <div className="mt-2 flex h-48 gap-2 border-b border-slate-100">
            {meses.map((m, index) => {
              const esMesActual = index === meses.length - 1
              return (
                // h-full + justify-end: la barra usa height en % (resuelve
                // contra la altura de ESTE div, no la del contenedor de
                // arriba) -- sin h-full acá, height:X% no tiene contra qué
                // resolver (altura "auto") y la barra queda invisible aunque
                // el cálculo del porcentaje esté bien.
                <div key={m.mes} className="group relative flex h-full flex-1 flex-col items-center justify-end">
                  {m.total > 0 && (
                    <span className="mb-1 text-[10px] font-medium text-slate-500 opacity-0 transition-opacity group-hover:opacity-100">
                      {m.total}
                    </span>
                  )}
                  <div
                    role="img"
                    aria-label={`${m.label}: ${m.total} incidentes`}
                    // minHeight con datos > 0 para que un mes con 1-2
                    // incidentes siga siendo visible junto a un mes con 40.
                    style={{ height: m.total > 0 ? `${Math.max((m.total / maxValue) * 100, 4)}%` : '2px' }}
                    className={`w-full rounded-t-sm transition-colors ${
                      m.total === 0 ? 'bg-slate-100' : esMesActual ? 'bg-red-400 group-hover:bg-red-500' : 'bg-slate-300 group-hover:bg-slate-400'
                    }`}
                  />
                </div>
              )
            })}
          </div>
          <div className="mt-1.5 flex gap-2">
            {meses.map((m) => (
              <span key={m.mes} className="flex-1 text-center text-[10px] text-slate-400 capitalize">
                {m.label}
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
