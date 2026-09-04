import { infractionTypes } from '../data/mockReports'

export function InfractionsBreakdown() {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-5">
      <h2 className="text-sm font-semibold text-slate-900">Tipos de Infracciones</h2>

      <div className="mt-4 flex justify-center">
        <div className="flex h-32 w-32 items-center justify-center rounded-full border-8 border-slate-100">
          <div className="flex h-full w-full items-center justify-center rounded-full border border-slate-200">
            <span className="text-lg font-bold text-slate-900">1,245</span>
          </div>
        </div>
      </div>

      <ul className="mt-5 flex flex-col gap-2.5">
        {infractionTypes.map((type) => (
          <li key={type.label} className="flex items-center justify-between text-sm">
            <span className="flex items-center gap-2 text-slate-600">
              <span className={`h-2.5 w-2.5 rounded-full ${type.color}`} />
              {type.label}
            </span>
            <span className="font-semibold text-slate-800">{type.percentage}%</span>
          </li>
        ))}
      </ul>
    </div>
  )
}
