import { useState } from 'react'
import { Badge } from '../../../components/ui/Badge'
import { BanIcon, EyeIcon, ShipIcon } from '../../../components/icons'
import type { Incident, IncidentSeverity } from '../data/mockIncidents'
import { IncidentDetailModal } from './IncidentDetailModal'

const severityConfig: Record<IncidentSeverity, { label: string; variant: 'red' | 'amber' | 'gray' }> = {
  alto: { label: 'Alto', variant: 'red' },
  medio: { label: 'Medio', variant: 'amber' },
  bajo: { label: 'Bajo', variant: 'gray' },
}

interface IncidentsTableProps {
  incidents: Incident[]
  onDescartar: (id: string) => Promise<void>
}

export function IncidentsTable({ incidents, onDescartar }: IncidentsTableProps) {
  const [seleccionado, setSeleccionado] = useState<Incident | null>(null)
  const [descartando, setDescartando] = useState<string | null>(null)
  const [errorDescarte, setErrorDescarte] = useState<string | null>(null)

  async function handleDescartar(incident: Incident) {
    if (!window.confirm(`¿Descartar el incidente ${incident.id}? Esta acción no se puede deshacer.`)) return
    setDescartando(incident.id)
    setErrorDescarte(null)
    try {
      await onDescartar(incident.id)
    } catch (err) {
      setErrorDescarte(err instanceof Error ? err.message : 'Error desconocido')
    } finally {
      setDescartando(null)
    }
  }

  return (
    <div className="overflow-x-auto">
      {errorDescarte && <p className="px-4 pt-3 text-sm text-red-600">{errorDescarte}</p>}
      <table className="w-full text-left text-sm">
        <thead>
          <tr className="border-b border-slate-200 text-[11px] font-semibold tracking-wide text-slate-400 uppercase">
            <th className="px-4 py-3">ID Incidente</th>
            <th className="px-4 py-3">Embarcación</th>
            <th className="px-4 py-3">Tipo de Infracción</th>
            <th className="px-4 py-3">Fecha y Hora (UTC-5)</th>
            <th className="px-4 py-3">Gravedad</th>
            <th className="px-4 py-3">Acciones</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          {incidents.map((incident) => {
            const severity = severityConfig[incident.severity]
            return (
              <tr key={incident.id} className="hover:bg-slate-50">
                <td className="px-4 py-3 font-medium text-slate-700">{incident.id}</td>
                <td className="px-4 py-3">
                  <div className="flex items-center gap-2">
                    <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-slate-100 text-slate-500">
                      <ShipIcon className="h-4 w-4" />
                    </span>
                    <div className="leading-tight">
                      <p className="font-medium text-slate-800">{incident.vessel}</p>
                      <p className="text-xs text-slate-400">{incident.vesselCode}</p>
                    </div>
                  </div>
                </td>
                <td className="max-w-xs truncate px-4 py-3 text-slate-600">{incident.infraction}</td>
                <td className="px-4 py-3 text-slate-500">{incident.dateTime}</td>
                <td className="px-4 py-3">
                  <Badge variant={severity.variant}>{severity.label}</Badge>
                </td>
                <td className="px-4 py-3">
                  <div className="flex items-center gap-3">
                    <button
                      onClick={() => setSeleccionado(incident)}
                      aria-label="Ver incidente"
                      className="text-slate-400 hover:text-slate-700"
                    >
                      <EyeIcon className="h-4 w-4" />
                    </button>
                    <button
                      onClick={() => void handleDescartar(incident)}
                      disabled={descartando === incident.id}
                      aria-label="Descartar incidente"
                      className="text-red-400 hover:text-red-600 disabled:cursor-not-allowed disabled:opacity-40"
                    >
                      <BanIcon className="h-4 w-4" />
                    </button>
                  </div>
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>

      {seleccionado && <IncidentDetailModal incident={seleccionado} onClose={() => setSeleccionado(null)} />}
    </div>
  )
}
