import { CircleDotIcon, SparklesIcon } from '../../../components/icons'
import type { Sugerencia } from '../hooks/useSugerencias'

const dotClasses: Record<string, string> = {
  red: 'text-red-500',
  amber: 'text-amber-500',
  gray: 'text-slate-400',
  dark: 'text-slate-700',
}

function formatearTiempo(iso: string): string {
  const minutos = Math.max(0, Math.round((Date.now() - new Date(iso).getTime()) / 60000))
  if (minutos < 1) return 'Hace instantes'
  if (minutos < 60) return `Hace ${minutos} min`
  return `Hace ${Math.round(minutos / 60)} h`
}

interface ValidationCardProps {
  item: Sugerencia
  onAprobar: () => void
  onRechazar: () => void
  procesando: boolean
}

export function ValidationCard({ item, onAprobar, onRechazar, procesando }: ValidationCardProps) {
  return (
    <div className="rounded-xl border border-l-4 border-slate-200 border-l-red-500 bg-white p-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-[11px] font-medium text-slate-400 uppercase">
            {formatearTiempo(item.creado_en)} · {item.dominio}
          </p>
          <h3 className="mt-1 text-sm font-semibold text-slate-900">{item.titular}</h3>
        </div>
        <span className="shrink-0 rounded bg-red-100 px-2 py-1 text-[10px] font-bold tracking-wide text-red-700 uppercase">
          Extracción Exitosa
        </span>
      </div>

      <div className="mt-3 rounded-lg bg-slate-50 p-3">
        <p className="flex items-center gap-1.5 text-[11px] font-semibold tracking-wide text-slate-500 uppercase">
          <SparklesIcon className="h-3.5 w-3.5" />
          Incidente sugerido por IA
        </p>

        <div className="mt-2 grid grid-cols-2 gap-3">
          <div>
            <p className="text-[10px] font-semibold tracking-wide text-slate-400 uppercase">Tipo de infracción</p>
            <p className="mt-0.5 flex items-center gap-1.5 text-xs font-medium text-slate-700">
              <CircleDotIcon className={`h-3 w-3 ${dotClasses[item.color_indicador ?? 'gray']}`} />
              {item.tipo_infraccion_nombre ?? 'No determinado'}
            </p>
          </div>
          <div>
            <p className="text-[10px] font-semibold tracking-wide text-slate-400 uppercase">Ubicación estimada</p>
            <p className="mt-0.5 text-xs font-medium text-slate-700">{item.ubicacion_estimada ?? 'No determinada'}</p>
          </div>
        </div>

        {item.resumen ? (
          <div className="mt-3">
            <p className="text-[10px] font-semibold tracking-wide text-slate-400 uppercase">Resumen de contexto</p>
            <p className="mt-0.5 text-xs leading-relaxed text-slate-600">{item.resumen}</p>
          </div>
        ) : null}

        {!item.tipo_infraccion_id && (
          <p className="mt-2 text-[11px] text-amber-600">
            La IA no pudo determinar el tipo de infracción; se debe indicar manualmente antes de aprobar.
          </p>
        )}
      </div>

      <div className="mt-3 flex items-center gap-2">
        <button
          type="button"
          onClick={onAprobar}
          disabled={procesando || !item.tipo_infraccion_id}
          className="flex-1 rounded-lg bg-slate-900 px-3 py-2 text-xs font-semibold text-white hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-50"
        >
          Aprobar
        </button>
        <button
          type="button"
          onClick={onRechazar}
          disabled={procesando}
          className="flex-1 rounded-lg border border-slate-300 px-3 py-2 text-xs font-semibold text-slate-600 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50"
        >
          Rechazar
        </button>
      </div>
    </div>
  )
}
