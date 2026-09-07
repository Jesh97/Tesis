import { AlertTriangleIcon, CompassIcon, GaugeIcon, HistoryIcon, XIcon } from '../../../components/icons'

interface AlertCardProps {
  vessel: string
  matricula: string
  description: string
  speedKnots?: number
  headingDegrees?: number
  heading?: string
  latitude: string
  longitude: string
  onClose?: () => void
  onRegister?: () => void
}

export function AlertCard({
  vessel,
  matricula,
  description,
  speedKnots,
  headingDegrees,
  heading,
  latitude,
  longitude,
  onClose,
  onRegister,
}: AlertCardProps) {
  return (
    <div className="absolute top-4 right-4 z-[1000] w-80 overflow-hidden rounded-xl border border-slate-200 bg-white shadow-lg">
      <div className="flex items-center justify-between border-b border-red-100 bg-red-50 px-4 py-2.5">
        <div className="flex items-center gap-2 text-sm font-semibold text-red-700">
          <AlertTriangleIcon className="h-4 w-4" />
          Alerta de Monitoreo
        </div>
        <button onClick={onClose} aria-label="Cerrar" className="text-red-400 hover:text-red-600">
          <XIcon className="h-4 w-4" />
        </button>
      </div>

      <div className="px-4 pt-3">
        <div className="flex items-center justify-between">
          <h3 className="text-base font-bold text-slate-900">{vessel}</h3>
          <span className="rounded bg-red-100 px-2 py-0.5 text-[10px] font-bold tracking-wide text-red-700 uppercase">
            Sospechoso
          </span>
        </div>
        <p className="mt-0.5 text-xs text-slate-500"># Matrícula: {matricula}</p>

        <p className="mt-3 rounded-lg bg-slate-50 p-2.5 text-xs leading-relaxed text-slate-600">
          {description}
        </p>

        <div className="mt-3 grid grid-cols-2 gap-3">
          <div>
            <p className="text-[10px] font-semibold tracking-wide text-slate-400 uppercase">Velocidad</p>
            <p className="mt-0.5 flex items-center gap-1 text-sm font-medium text-slate-700">
              <GaugeIcon className="h-3.5 w-3.5 text-slate-400" />
              {speedKnots != null ? `${speedKnots} nds` : 'N/D'}
            </p>
          </div>
          <div>
            <p className="text-[10px] font-semibold tracking-wide text-slate-400 uppercase">Rumbo</p>
            <p className="mt-0.5 flex items-center gap-1 text-sm font-medium text-slate-700">
              <CompassIcon className="h-3.5 w-3.5 text-slate-400" />
              {headingDegrees != null ? `${headingDegrees}° ${heading ?? ''}` : 'N/D'}
            </p>
          </div>
          <div>
            <p className="text-[10px] font-semibold tracking-wide text-slate-400 uppercase">Latitud</p>
            <p className="mt-0.5 text-sm font-medium text-slate-700">{latitude}</p>
          </div>
          <div>
            <p className="text-[10px] font-semibold tracking-wide text-slate-400 uppercase">Longitud</p>
            <p className="mt-0.5 text-sm font-medium text-slate-700">{longitude}</p>
          </div>
        </div>
      </div>

      <div className="flex items-center gap-2 p-4">
        <button
          onClick={onRegister}
          className="flex flex-1 items-center justify-center gap-2 rounded-lg bg-red-700 px-4 py-2.5 text-xs font-semibold tracking-wide text-white uppercase hover:bg-red-800"
        >
          Registrar incidente
        </button>
        <button
          aria-label="Historial"
          className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg border border-slate-200 text-slate-500 hover:bg-slate-50"
        >
          <HistoryIcon className="h-4 w-4" />
        </button>
      </div>
    </div>
  )
}
