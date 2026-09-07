import type { TipoInfraccionResumen } from '../hooks/useReportes'

const colorClasses: Record<TipoInfraccionResumen['color_indicador'], string> = {
  red: 'bg-red-500',
  amber: 'bg-amber-400',
  gray: 'bg-slate-300',
  dark: 'bg-slate-900',
}

export function InfractionsBreakdown({ data }: { data: TipoInfraccionResumen[] }) {
  const total = data.reduce((suma, d) => suma + d.total, 0)

  return (
    <div className="rounded-xl border border-slate-200 bg-white p-5">
      <h2 className="text-sm font-semibold text-slate-900">Tipos de Infracciones</h2>

      <div className="mt-4 flex justify-center">
        <div className="flex h-32 w-32 items-center justify-center rounded-full border-8 border-slate-100">
          <div className="flex h-full w-full items-center justify-center rounded-full border border-slate-200">
            <span className="text-lg font-bold text-slate-900">{total.toLocaleString('es-PE')}</span>
          </div>
        </div>
      </div>

      {total === 0 ? (
        <p className="mt-5 text-center text-sm text-slate-400">Todavía no hay incidentes registrados.</p>
      ) : (
        <ul className="mt-5 flex flex-col gap-2.5">
          {data.map((tipo) => (
            <li key={tipo.nombre} className="flex items-center justify-between text-sm">
              <span className="flex items-center gap-2 text-slate-600">
                <span className={`h-2.5 w-2.5 rounded-full ${colorClasses[tipo.color_indicador]}`} />
                {tipo.nombre}
              </span>
              <span className="font-semibold text-slate-800">{tipo.porcentaje ?? 0}%</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
