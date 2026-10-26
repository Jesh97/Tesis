import { useEffect, useState } from 'react'
import { apiFetch } from '../../../lib/api'

export interface BuqueTop {
  vesselId: string
  nombre: string | null
  mmsi: string | null
  flag: string | null
  horas: number
}

/** Un mes de /api/actividad/mensual -- ver agregar_por_mes en
 * server/app/actividad_mensual.py para qué mide cada campo. */
export interface ActividadMes {
  mes: string // AAAA-MM
  parcial: boolean
  buquesPresentes: number
  horasPresencia: number
  porTipo: Record<string, number>
  pesquerosPresentes: number
  pesquerosExtranjeros: number
  porBanderaPesqueros: Record<string, number>
  buquesPescando: number
  horasPesca: number
  celdas: [number, number, number][] // [lat, lon, horas]
  topBuques: BuqueTop[]
}

interface RespuestaActividad {
  desde: string
  hasta: string
  meses: ActividadMes[]
}

interface IncidenteMes {
  mes: string // AAAA-MM-DD (primer día del mes)
  total: number
}

/** Actividad AIS mes a mes de GFW + incidentes registrados en el mismo rango.
 * Se piden en paralelo pero fallan por separado: si la base de datos no
 * responde, el resto de la vista (que solo depende de GFW) se sigue viendo. */
export function useActividadMensual(desde: string, hasta: string) {
  const [meses, setMeses] = useState<ActividadMes[]>([])
  const [incidentesPorMes, setIncidentesPorMes] = useState<Record<string, number> | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let ignore = false

    async function load() {
      setLoading(true)
      setError(null)
      const params = new URLSearchParams({ desde, hasta })
      const paramsIncidentes = new URLSearchParams({ desde: `${desde}-01`, hasta: `${hasta}-01` })

      const [actividad, incidentes] = await Promise.allSettled([
        apiFetch(`/api/actividad/mensual?${params}`).then(async (r) => {
          const data = await r.json()
          if (!r.ok) throw new Error(data?.error ?? `Error ${r.status} al consultar GFW`)
          return data as RespuestaActividad
        }),
        apiFetch(`/api/reportes/incidentes-por-mes-rango?${paramsIncidentes}`).then(async (r) => {
          if (!r.ok) throw new Error(`Error ${r.status}`)
          return (await r.json()) as IncidenteMes[]
        }),
      ])

      if (ignore) return
      if (actividad.status === 'fulfilled') {
        setMeses(actividad.value.meses)
      } else {
        setMeses([])
        setError(actividad.reason instanceof Error ? actividad.reason.message : 'Error desconocido')
      }
      setIncidentesPorMes(
        incidentes.status === 'fulfilled'
          ? Object.fromEntries(incidentes.value.map((i) => [i.mes.slice(0, 7), i.total]))
          : null,
      )
      setLoading(false)
    }

    void load()
    return () => {
      ignore = true
    }
  }, [desde, hasta])

  return { meses, incidentesPorMes, loading, error }
}
