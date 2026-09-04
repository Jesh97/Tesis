import { useEffect, useState } from 'react'

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

/** Barcos detectados por Global Fishing Watch frente a la costa de Lambayeque (últimos 7 días). */
export function useLambayequeVessels() {
  const [vessels, setVessels] = useState<LambayequeVessel[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const controller = new AbortController()

    async function load() {
      setLoading(true)
      setError(null)
      try {
        const response = await fetch('/api/embarcaciones/gfw/lambayeque', { signal: controller.signal })
        if (!response.ok) {
          const body = (await response.json().catch(() => null)) as { error?: string } | null
          throw new Error(body?.error ?? `Error ${response.status} al consultar embarcaciones`)
        }
        const data = (await response.json()) as LambayequeResponse
        setVessels(data.barcos)
      } catch (err) {
        if (err instanceof DOMException && err.name === 'AbortError') return
        setError(err instanceof Error ? err.message : 'Error desconocido')
      } finally {
        setLoading(false)
      }
    }

    void load()
    return () => controller.abort()
  }, [])

  return { vessels, loading, error }
}
