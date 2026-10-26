import { useEffect, useState } from 'react'
import { apiFetch } from '../../../lib/api'

export interface ActividadSospechosa {
  mmsi: string
  nombre: string
  flag: string | null
  lat: number
  lon: number
  apagonAis: { detectado: true; diasSinSenal: number; probabilidad: number } | null
  /** Días seguidos sin tocar puerto ni desembarcadero (regla) o detector
   * entrenado; `alMenos`: no se lo vio en puerto en toda la racha observada. */
  demoraPuerto: { detectado: true; diasLejosDePuerto: number; alMenos: boolean; porRegla: boolean; probabilidad: number } | null
  /** Pesca aparente dentro de las 5 mn de la costa continental (regla) o
   * detector entrenado "zona_protegida". */
  reservaArtesanal: { detectado: true; diasPescando: number; distCostaMinNm: number | null; porRegla: boolean; probabilidad: number } | null
  /** Pesca aparente junto a las islas Lobos de Tierra / Lobos de Afuera (RNSIIPG). */
  islasProtegidas: { detectado: true; diasPescando: number; distIslaMinNm: number } | null
  cruceFronteraZee: {
    detectado: true
    distCostaAntesNm: number
    distCostaAhoraNm: number
    diasSinSenal: number
    probabilidad: number
  } | null
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
 * Embarcaciones con apagón de AIS, demora en puerto, pesca en la reserva de
 * 5 mn o junto a las islas Lobos, a partir de features reconstruidas desde
 * datos en vivo de GFW. Cada patrón combina una regla con el detector
 * entrenado -- ver server/app/deteccion.py.
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
