import { useState } from 'react'
import { apiFetch } from '../../../lib/api'

export interface DatosReporteManual {
  tipoInfraccionId: string
  descripcion: string
  gravedad?: 'alto' | 'medio' | 'bajo'
  mmsi?: string
  vessel?: string
  fecha?: string
}

/** "Reportar incidencia" (sidebar): registra un incidente manual, elegido a
 * mano del catálogo -- para cuando el analista se entera por otra vía
 * (llamada, denuncia, inspección), no desde una alerta automática del mapa. */
export function useReportarIncidente() {
  const [enviando, setEnviando] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function reportar(datos: DatosReporteManual): Promise<string | null> {
    setEnviando(true)
    setError(null)
    try {
      const response = await apiFetch('/api/incidentes', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(datos),
      })
      if (!response.ok) {
        const body = (await response.json().catch(() => null)) as { error?: string } | null
        throw new Error(body?.error ?? `Error ${response.status} al registrar el incidente`)
      }
      const data = (await response.json()) as { incidente: { id: string; codigo: string } }
      return data.incidente.codigo
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error desconocido')
      return null
    } finally {
      setEnviando(false)
    }
  }

  return { reportar, enviando, error }
}
