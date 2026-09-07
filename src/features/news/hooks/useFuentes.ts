import { useCallback, useEffect, useState } from 'react'
import { apiFetch } from '../../../lib/api'

export interface Fuente {
  id: string
  url: string
  dominio: string
  estado: 'pendiente' | 'procesando' | 'exitosa' | 'fallida'
  creado_en: string
  procesado_en: string | null
}

/** Fuentes de noticias enviadas al Analizador Web (ver
 * server/app/routes/fuentes.py). */
export function useFuentes() {
  const [fuentes, setFuentes] = useState<Fuente[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const recargar = useCallback(async () => {
    setError(null)
    try {
      const response = await apiFetch('/api/fuentes')
      if (!response.ok) throw new Error(`Error ${response.status} al listar fuentes`)
      setFuentes((await response.json()) as Fuente[])
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error desconocido')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void recargar()
    const intervalo = setInterval(() => void recargar(), 5000)
    return () => clearInterval(intervalo)
  }, [recargar])

  async function analizar(urls: string[]): Promise<void> {
    const response = await apiFetch('/api/fuentes/analizar', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ urls }),
    })
    if (!response.ok) {
      const body = (await response.json().catch(() => null)) as { error?: string } | null
      throw new Error(body?.error ?? `Error ${response.status} al iniciar el análisis`)
    }
    await recargar()
  }

  return { fuentes, loading, error, analizar }
}
