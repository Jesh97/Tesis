import { useEffect, useState } from 'react'
import { apiFetch } from '../../../lib/api'

export interface LambayequeVessel {
  embarcacionId: string | null
  nombre: string
  mmsi: string | null
  flag: string | null
  vesselType: string | null
  lat: number
  lon: number
  horas: number
}

interface LambayequeResponse {
  desde: string
  hasta: string
  total: number
  barcos: LambayequeVessel[]
}

/**
 * Barcos reportados por Global Fishing Watch en el mar peruano para un rango
 * de fechas. GFW no da datos en tiempo real: su dataset público de esfuerzo
 * pesquero se completa retroactivamente durante semanas/meses, así que los
 * últimos días casi siempre vienen vacíos (ver desde/hasta para elegir una
 * ventana con mejor cobertura).
 */
export function useLambayequeVessels(desde?: string, hasta?: string) {
  const [vessels, setVessels] = useState<LambayequeVessel[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let ignore = false

    async function load() {
      setLoading(true)
      setError(null)
      try {
        const params = new URLSearchParams()
        if (desde) params.set('desde', desde)
        if (hasta) params.set('hasta', hasta)
        const query = params.toString()
        const response = await apiFetch(`/api/embarcaciones/gfw/lambayeque${query ? `?${query}` : ''}`)
        if (!response.ok) {
          const body = (await response.json().catch(() => null)) as { error?: string } | null
          throw new Error(body?.error ?? `Error ${response.status} al consultar embarcaciones`)
        }
        const data = (await response.json()) as LambayequeResponse
        if (!ignore) setVessels(data.barcos)
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
  }, [desde, hasta])

  return { vessels, loading, error }
}
