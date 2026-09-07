import { useEffect, useState } from 'react'
import { apiFetch } from '../../../lib/api'

export interface ActividadSospechosa {
  mmsi: string
  nombre: string
  flag: string | null
  lat: number
  lon: number
  apagonAis: { detectado: true; diasSinSenal: number; probabilidad: number } | null
  demoraPuerto: { detectado: true; diasLejosDePuerto: number; probabilidad: number } | null
}

export interface ZonaConActividad {
  zonaId: string
  zonaNombre: string
  region: string
  barcos: ActividadSospechosa[]
  error: string | null
}

interface ActividadResponse {
  desde: string
  hasta: string
  zonas: ZonaConActividad[]
}

/**
 * Embarcaciones marcadas por los detectores entrenados "apagon_ais" y
 * "demora_puerto" (server/app/modelo.py), alimentados con features
 * reconstruidas desde datos en vivo de GFW. Ver server/app/features.py para
 * el detalle de qué se pudo y no se pudo reconstruir fielmente.
 */
export function useActividadSospechosaAlertas() {
  const [zonas, setZonas] = useState<ZonaConActividad[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let ignore = false

    async function load() {
      setLoading(true)
      setError(null)
      try {
        const response = await apiFetch('/api/irregularidades/actividad')
        if (!response.ok) {
          const body = (await response.json().catch(() => null)) as { error?: string } | null
          throw new Error(body?.error ?? `Error ${response.status} al consultar irregularidades`)
        }
        const data = (await response.json()) as ActividadResponse
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
