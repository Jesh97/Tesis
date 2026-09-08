import { useState } from 'react'
import { apiFetch } from '../../../lib/api'

export interface EmbarcacionEncontrada {
  nombre: string | null
  mmsi: string | null
  flag: string | null
  vesselType: string | null
  tipo: string
  lat: number
  lon: number
}

interface BuscarResponse {
  encontrado: boolean
  barco?: EmbarcacionEncontrada
}

/** Botón "Buscar en GFW" del formulario "Reportar Incidencia": a partir del
 * mmsi o el nombre ya escritos a mano, busca la embarcación en el dataset de
 * GFW (GET /api/embarcaciones/buscar) para traer su posición y datos
 * adicionales (bandera, tipo) sin que el analista tenga que ubicarla a mano. */
export function useBuscarEmbarcacion() {
  const [buscando, setBuscando] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function buscar(params: { mmsi?: string; nombre?: string }): Promise<EmbarcacionEncontrada | null> {
    setBuscando(true)
    setError(null)
    try {
      const query = new URLSearchParams()
      if (params.mmsi) query.set('mmsi', params.mmsi)
      if (params.nombre) query.set('nombre', params.nombre)
      const response = await apiFetch(`/api/embarcaciones/buscar?${query.toString()}`)
      if (!response.ok) {
        const body = (await response.json().catch(() => null)) as { error?: string } | null
        throw new Error(body?.error ?? `Error ${response.status} al buscar la embarcación`)
      }
      const data = (await response.json()) as BuscarResponse
      return data.encontrado && data.barco ? data.barco : null
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error desconocido')
      return null
    } finally {
      setBuscando(false)
    }
  }

  return { buscar, buscando, error }
}
