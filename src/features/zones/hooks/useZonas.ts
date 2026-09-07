import { useCallback, useEffect, useState } from 'react'
import { apiFetch } from '../../../lib/api'

export interface Coordenada {
  lat: number
  lon: number
}

export interface Zona {
  id: string
  nombre: string
  region: string
  es_critica: boolean
  poligono: { type: 'Polygon'; coordinates: number[][][] } | null
  creado_en: string
}

export function useZonas() {
  const [zonas, setZonas] = useState<Zona[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const recargar = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const response = await apiFetch('/api/zonas')
      if (!response.ok) throw new Error(`Error ${response.status} al listar zonas`)
      setZonas((await response.json()) as Zona[])
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error desconocido')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void recargar()
  }, [recargar])

  async function crearZona(datos: { nombre: string; region: string; esCritica: boolean; coordenadas: Coordenada[] }) {
    const response = await apiFetch('/api/zonas', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(datos),
    })
    if (!response.ok) {
      const body = (await response.json().catch(() => null)) as { error?: string } | null
      throw new Error(body?.error ?? `Error ${response.status} al crear la zona`)
    }
    await recargar()
  }

  async function eliminarZona(id: string) {
    const response = await apiFetch(`/api/zonas/${id}`, { method: 'DELETE' })
    if (!response.ok) throw new Error(`Error ${response.status} al eliminar la zona`)
    await recargar()
  }

  return { zonas, loading, error, crearZona, eliminarZona }
}
