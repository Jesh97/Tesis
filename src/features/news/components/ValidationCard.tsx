import { CircleDotIcon, SparklesIcon } from '../../../components/icons'
import type { ValidationItem } from '../data/mockValidationItems'

const accentClasses = {
  red: {
    border: 'border-l-red-500',
    badge: 'bg-red-100 text-red-700',
  },
  blue: {
    border: 'border-l-sky-500',
    badge: 'bg-sky-100 text-sky-700',
  },
}

const dotClasses = {
  red: 'text-red-500',
  amber: 'text-amber-500',
}

export function ValidationCard({ item }: { item: ValidationItem }) {
  const accent = accentClasses[item.accent]

  return (
    <div className={`rounded-xl border border-l-4 border-slate-200 bg-white p-4 ${accent.border}`}>
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-[11px] font-medium text-slate-400 uppercase">
            {item.timeAgo} · {item.source}
          </p>
          <h3 className="mt-1 text-sm font-semibold text-slate-900">{item.headline}</h3>
        </div>
        <span className={`shrink-0 rounded px-2 py-1 text-[10px] font-bold tracking-wide uppercase ${accent.badge}`}>
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
              <CircleDotIcon className={`h-3 w-3 ${dotClasses[item.infractionDotColor]}`} />
              {item.infractionType}
            </p>
          </div>
          <div>
            <p className="text-[10px] font-semibold tracking-wide text-slate-400 uppercase">{item.detail.label}</p>
            <p className="mt-0.5 text-xs font-medium text-slate-700">{item.detail.value}</p>
          </div>
        </div>

        {item.summary ? (
          <div className="mt-3">
            <p className="text-[10px] font-semibold tracking-wide text-slate-400 uppercase">Resumen de contexto</p>
            <p className="mt-0.5 text-xs leading-relaxed text-slate-600">{item.summary}</p>
          </div>
        ) : null}
      </div>
    </div>
  )
}
