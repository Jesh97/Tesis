import { useState } from 'react'
import { apiFetch } from '../../../lib/api'

export type TipoAlerta = 'zona_protegida' | 'apagon_ais' | 'demora_puerto'

export interface DatosIncidenteDesdeAlerta {
  tipoAlerta: TipoAlerta
  descripcion: string
  mmsi: string | null
  vessel: string
  lat: number
  lon: number
}

/** Registra un incidente real a partir de una alerta del mapa (botón
 * "Registrar incidente" en AlertCard) -- POST /api/incidentes. */
export function useRegistrarIncidente() {
  const [registrando, setRegistrando] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function registrar(datos: DatosIncidenteDesdeAlerta): Promise<boolean> {
    setRegistrando(true)
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
      return true
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error desconocido')
      return false
    } finally {
      setRegistrando(false)
    }
  }

  return { registrar, registrando, error }
}
