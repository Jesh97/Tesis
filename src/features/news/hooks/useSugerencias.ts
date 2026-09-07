import { useCallback, useEffect, useState } from 'react'
import { apiFetch } from '../../../lib/api'

export interface Sugerencia {
  id: string
  fuente_id: string
  titular: string
  resumen: string | null
  tipo_infraccion_id: string | null
  tipo_infraccion_nombre: string | null
  color_indicador: 'red' | 'amber' | 'gray' | 'dark' | null
  embarcacion_detectada: string | null
  ubicacion_estimada: string | null
  confianza: number | null
  estado: 'pendiente' | 'aprobado' | 'rechazado'
  creado_en: string
  url: string
  dominio: string
}

/** Cola de Validación IA: sugerencias de incidente extraídas de noticias
 * (ver server/app/routes/sugerencias.py). */
export function useSugerencias() {
  const [sugerencias, setSugerencias] = useState<Sugerencia[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const recargar = useCallback(async () => {
    setError(null)
    try {
      const response = await apiFetch('/api/sugerencias')
      if (!response.ok) throw new Error(`Error ${response.status} al listar sugerencias`)
      setSugerencias((await response.json()) as Sugerencia[])
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error desconocido')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void recargar()
    // El análisis de noticias corre en segundo plano en el backend: se
    // refresca cada 5s para que las sugerencias nuevas aparezcan sin recargar.
    const intervalo = setInterval(() => void recargar(), 5000)
    return () => clearInterval(intervalo)
  }, [recargar])

  async function aprobar(id: string, tipoInfraccionId?: string): Promise<void> {
    const response = await apiFetch(`/api/sugerencias/${id}/aprobar`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(tipoInfraccionId ? { tipo_infraccion_id: tipoInfraccionId } : {}),
    })
    if (!response.ok) {
      const body = (await response.json().catch(() => null)) as { error?: string } | null
      throw new Error(body?.error ?? `Error ${response.status} al aprobar la sugerencia`)
    }
    await recargar()
  }

  async function rechazar(id: string): Promise<void> {
    const response = await apiFetch(`/api/sugerencias/${id}/rechazar`, { method: 'POST' })
    if (!response.ok) throw new Error(`Error ${response.status} al rechazar la sugerencia`)
    await recargar()
  }

  return { sugerencias, loading, error, aprobar, rechazar }
}
