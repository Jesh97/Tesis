import { topZones } from '../data/mockReports'

const rankClasses: Record<number, string> = {
  1: 'bg-red-500',
  2: 'bg-slate-900',
  3: 'bg-slate-400',
}

export function TopZones() {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-5">
      <h2 className="text-sm font-semibold text-slate-900">Zonas con Mayor Incidencia</h2>

      <div className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-3">
        {topZones.map((zone) => (
          <div key={zone.rank} className="flex items-center gap-3 rounded-lg border border-slate-200 p-3">
            <span
              className={`flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-xs font-bold text-white ${rankClasses[zone.rank]}`}
            >
              {zone.rank}
            </span>
            <div className="min-w-0 flex-1 leading-tight">
              <p className="truncate font-medium text-slate-800">{zone.name}</p>
              <p className="text-xs text-slate-400">{zone.region}</p>
            </div>
            <span className="shrink-0 text-sm font-semibold text-slate-700">{zone.incidents} inc.</span>
          </div>
        ))}
      </div>
    </div>
  )
}
