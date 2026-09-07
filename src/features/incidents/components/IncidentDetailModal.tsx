import { useEffect } from 'react'
import { Badge } from '../../../components/ui/Badge'
import { XIcon } from '../../../components/icons'
import type { Incident, IncidentSeverity } from '../data/mockIncidents'

const severityConfig: Record<IncidentSeverity, { label: string; variant: 'red' | 'amber' | 'gray' }> = {
  alto: { label: 'Alto', variant: 'red' },
  medio: { label: 'Medio', variant: 'amber' },
  bajo: { label: 'Bajo', variant: 'gray' },
}

const estadoLabel: Record<Incident['estado'], string> = {
  sospechoso: 'Sospechoso',
  confirmado: 'Confirmado',
  descartado: 'Descartado',
}

export function IncidentDetailModal({ incident, onClose }: { incident: Incident; onClose: () => void }) {
  useEffect(() => {
    function onKeyDown(e: KeyboardEvent) {
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [onClose])

  const severity = severityConfig[incident.severity]

  return (
    <div
      className="fixed inset-0 z-[2000] flex items-center justify-center bg-slate-900/40 p-4"
      onClick={onClose}
      role="presentation"
    >
      <div
        className="w-full max-w-md rounded-xl border border-slate-200 bg-white shadow-lg"
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-labelledby="incident-detail-title"
      >
        <div className="flex items-center justify-between border-b border-slate-200 px-5 py-3.5">
          <h2 id="incident-detail-title" className="text-sm font-semibold text-slate-900">
            Detalle del Incidente
          </h2>
          <button onClick={onClose} aria-label="Cerrar" className="text-slate-400 hover:text-slate-600">
            <XIcon className="h-4 w-4" />
          </button>
        </div>

        <div className="flex flex-col gap-3 px-5 py-4 text-sm">
          <div className="flex items-center justify-between">
            <span className="font-mono text-xs text-slate-400">{incident.id}</span>
            <Badge variant={severity.variant}>{severity.label}</Badge>
          </div>

          <div>
            <p className="text-[10px] font-semibold tracking-wide text-slate-400 uppercase">Embarcación</p>
            <p className="mt-0.5 font-medium text-slate-800">{incident.vessel}</p>
            <p className="text-xs text-slate-400">{incident.vesselCode}</p>
          </div>

          <div>
            <p className="text-[10px] font-semibold tracking-wide text-slate-400 uppercase">Infracción</p>
            <p className="mt-0.5 leading-relaxed text-slate-600">{incident.infraction}</p>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <p className="text-[10px] font-semibold tracking-wide text-slate-400 uppercase">Fecha de detección</p>
              <p className="mt-0.5 text-slate-700">{incident.dateTime}</p>
            </div>
            <div>
              <p className="text-[10px] font-semibold tracking-wide text-slate-400 uppercase">Estado</p>
              <p className="mt-0.5 text-slate-700">{estadoLabel[incident.estado]}</p>
            </div>
          </div>

          {incident.lat != null && incident.lon != null && (
            <div>
              <p className="text-[10px] font-semibold tracking-wide text-slate-400 uppercase">Posición registrada</p>
              <p className="mt-0.5 font-mono text-xs text-slate-600">
                {incident.lat.toFixed(4)}, {incident.lon.toFixed(4)}
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
