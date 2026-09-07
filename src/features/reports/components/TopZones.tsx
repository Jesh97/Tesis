import type { ZonaTop } from '../hooks/useReportes'

const rankClasses: Record<number, string> = {
  1: 'bg-red-500',
  2: 'bg-slate-900',
  3: 'bg-slate-400',
}

export function TopZones({ data }: { data: ZonaTop[] }) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-5">
      <h2 className="text-sm font-semibold text-slate-900">Zonas con Mayor Incidencia</h2>

      {data.length === 0 ? (
        <p className="mt-4 text-sm text-slate-400">Todavía no hay incidentes asociados a una zona.</p>
      ) : (
        <div className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-3">
          {data.map((zone) => (
            <div key={`${zone.nombre}-${zone.region}`} className="flex items-center gap-3 rounded-lg border border-slate-200 p-3">
              <span
                className={`flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-xs font-bold text-white ${rankClasses[zone.ranking] ?? 'bg-slate-300'}`}
              >
                {zone.ranking}
              </span>
              <div className="min-w-0 flex-1 leading-tight">
                <p className="truncate font-medium text-slate-800">{zone.nombre}</p>
                <p className="text-xs text-slate-400">{zone.region}</p>
              </div>
              <span className="shrink-0 text-sm font-semibold text-slate-700">{zone.total_incidentes} inc.</span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
