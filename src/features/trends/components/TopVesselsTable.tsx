import { etiquetaMesLarga } from '../meses'
import type { BuqueTop } from '../hooks/useActividadMensual'

interface TopVesselsTableProps {
  mes: string
  buques: BuqueTop[]
  mmsiConIncidente: Set<string>
}

export function TopVesselsTable({ mes, buques, mmsiConIncidente }: TopVesselsTableProps) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-5">
      <h2 className="text-sm font-semibold text-slate-900">
        Más horas de pesca · <span className="capitalize">{etiquetaMesLarga(mes)}</span>
      </h2>
      <p className="mt-0.5 text-xs text-slate-500">Embarcaciones con más pesca aparente ese mes.</p>

      {buques.length === 0 ? (
        <p className="mt-6 text-sm text-slate-400">Sin pesca aparente registrada este mes.</p>
      ) : (
        <table className="mt-4 w-full text-sm">
          <thead>
            <tr className="border-b border-slate-100 text-left text-[11px] font-semibold tracking-wide text-slate-400 uppercase">
              <th className="pb-2">Embarcación</th>
              <th className="pb-2">Bandera</th>
              <th className="pb-2 text-right">Horas</th>
            </tr>
          </thead>
          <tbody>
            {buques.map((b) => (
              <tr key={b.vesselId} className="border-b border-slate-50 last:border-0">
                <td className="py-2">
                  <p className="font-medium text-slate-800">{b.nombre ?? 'Sin nombre'}</p>
                  <p className="text-xs text-slate-400">
                    MMSI {b.mmsi ?? '—'}
                    {b.mmsi && mmsiConIncidente.has(b.mmsi) && (
                      <span className="ml-2 rounded bg-red-50 px-1.5 py-0.5 font-medium text-red-700">Con incidente</span>
                    )}
                  </p>
                </td>
                <td className="py-2 text-slate-600">{b.flag ?? '—'}</td>
                <td className="py-2 text-right font-medium text-slate-900 tabular-nums">
                  {b.horas.toLocaleString('es-PE', { maximumFractionDigits: 1 })}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  )
}
