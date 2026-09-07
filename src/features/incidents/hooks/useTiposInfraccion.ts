import { useEffect, useState } from 'react'
import { apiFetch } from '../../../lib/api'

export interface TipoInfraccion {
  id: string
  nombre: string
  gravedad_sugerida: 'alto' | 'medio' | 'bajo'
}

/** Catálogo de tipos de infracción, para el selector del formulario de
 * "Reportar incidencia". */
export function useTiposInfraccion() {
  const [tipos, setTipos] = useState<TipoInfraccion[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let ignore = false

    async function load() {
      setLoading(true)
      setError(null)
      try {
        const response = await apiFetch('/api/incidentes/tipos-infraccion')
        if (!response.ok) throw new Error(`Error ${response.status} al listar tipos de infracción`)
        const data = (await response.json()) as TipoInfraccion[]
        if (!ignore) setTipos(data)
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

  return { tipos, loading, error }
}
