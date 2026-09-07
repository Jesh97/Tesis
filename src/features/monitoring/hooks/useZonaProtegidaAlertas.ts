import { useEffect, useState } from 'react'
import { apiFetch } from '../../../lib/api'

export interface EmbarcacionEnZona {
  embarcacionId: string | null
  nombre: string
  mmsi: string | null
  flag: string | null
  vesselType: string | null
  lat: number
  lon: number
  horas: number
  /** Probabilidad del detector "zona_protegida" entrenado (server/app/modelo.py)
   * de que la embarcación esté operando en la reserva artesanal -- señal
   * redundante al geofencing exacto que ya identificó a este barco.
   * `null` si no hubo suficiente historial diario para calcularla. */
  probabilidadModelo: number | null
}

export interface ZonaConBarcos {
  zonaId: string
  zonaNombre: string
  region: string
  barcos: EmbarcacionEnZona[]
  error: string | null
}

interface ZonaProtegidaResponse {
  desde: string
  hasta: string
  zonas: ZonaConBarcos[]
}

/** Embarcaciones detectadas por GFW dentro de zonas marcadas como críticas (patrón "zona_protegida"). */
export function useZonaProtegidaAlertas() {
  const [zonas, setZonas] = useState<ZonaConBarcos[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let ignore = false

    async function load() {
      setLoading(true)
      setError(null)
      try {
        const response = await apiFetch('/api/irregularidades/zona-protegida')
        if (!response.ok) {
          const body = (await response.json().catch(() => null)) as { error?: string } | null
          throw new Error(body?.error ?? `Error ${response.status} al consultar irregularidades`)
        }
        const data = (await response.json()) as ZonaProtegidaResponse
        if (!ignore) setZonas(data.zonas)
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

  return { zonas, loading, error }
}
