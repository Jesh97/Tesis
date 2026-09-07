import { useEffect, useState } from 'react'
import { apiFetch } from '../../../lib/api'

export interface ResumenReportes {
  total_incidentes: number
  embarcaciones_capturadas: number
  alertas_procesadas: number
  zonas_criticas: number
}

export interface IncidentePorMes {
  mes: string
  total: number
}

export interface TipoInfraccionResumen {
  nombre: string
  color_indicador: 'red' | 'amber' | 'gray' | 'dark'
  total: number
  porcentaje: number | null
}

export interface ZonaTop {
  nombre: string
  region: string
  total_incidentes: number
  ranking: number
}

/** Alimenta el Dashboard de Reportes con las vistas reales de la base de
 * datos (vw_reportes_resumen, vw_incidentes_por_mes, vw_tipos_infraccion_resumen,
 * vw_zonas_top en db/schema.sql), en vez de data/mockReports.ts. */
export function useReportes() {
  const [resumen, setResumen] = useState<ResumenReportes | null>(null)
  const [incidentesPorMes, setIncidentesPorMes] = useState<IncidentePorMes[]>([])
  const [tiposInfraccion, setTiposInfraccion] = useState<TipoInfraccionResumen[]>([])
  const [zonasTop, setZonasTop] = useState<ZonaTop[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let ignore = false

    async function load() {
      setLoading(true)
      setError(null)
      try {
        const [resResumen, resMeses, resTipos, resZonas] = await Promise.all([
          apiFetch('/api/reportes/resumen'),
          apiFetch('/api/reportes/incidentes-por-mes'),
          apiFetch('/api/reportes/tipos-infraccion'),
          apiFetch('/api/reportes/zonas-top'),
        ])
        for (const r of [resResumen, resMeses, resTipos, resZonas]) {
          if (!r.ok) throw new Error(`Error ${r.status} al cargar los reportes`)
        }
        const [resumenData, mesesData, tiposData, zonasData] = (await Promise.all([
          resResumen.json(),
          resMeses.json(),
          resTipos.json(),
          resZonas.json(),
        ])) as [ResumenReportes, IncidentePorMes[], TipoInfraccionResumen[], ZonaTop[]]

        if (!ignore) {
          setResumen(resumenData)
          setIncidentesPorMes(mesesData)
          setTiposInfraccion(tiposData)
          setZonasTop(zonasData)
        }
      } catch (err) {
        if (!ignore) setError(err instanceof Error ? err.message : 'Error desconocido')
      } finally {
        if (!ignore) setLoading(false)
      }
    }

    void load()
    return () => {
      ignore = true
    }
  }, [])

  return { resumen, incidentesPorMes, tiposInfraccion, zonasTop, loading, error }
}
