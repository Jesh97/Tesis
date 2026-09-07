import { AlertTriangleIcon, LoaderIcon } from '../../../components/icons'
import type { Fuente } from '../hooks/useFuentes'

export function ProcessingRow({ item }: { item: Fuente }) {
  const fallo = item.estado === 'fallida'
  return (
    <div className="flex items-center gap-3 rounded-xl border border-slate-200 bg-white p-4">
      <span
        className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-full ${
          fallo ? 'bg-red-100 text-red-500' : 'bg-slate-100 text-slate-400'
        }`}
      >
        {fallo ? <AlertTriangleIcon className="h-4 w-4" /> : <LoaderIcon className="h-4 w-4 animate-spin" />}
      </span>
      <div className="min-w-0 flex-1">
        <p className="truncate text-sm font-medium text-slate-700">
          {fallo ? 'Falló el análisis:' : 'Procesando:'} {item.dominio}
        </p>
        <p className="text-[11px] tracking-wide text-slate-400 uppercase">
          {fallo ? 'No se pudo extraer o analizar el contenido' : 'Extrayendo contenido y analizando con IA…'}
        </p>
      </div>
      <span
        className={`shrink-0 rounded px-2 py-1 text-[10px] font-bold tracking-wide uppercase ${
          fallo ? 'bg-red-100 text-red-600' : 'bg-slate-100 text-slate-500'
        }`}
      >
        {fallo ? 'Fallida' : 'En Proceso'}
      </span>
    </div>
  )
}
