import { useCallback, useEffect, useState } from 'react'
import { apiFetch } from '../../../lib/api'
import type { Incident } from '../data/mockIncidents'

export interface FiltrosIncidentes {
  desde?: string
  hasta?: string
  tipo?: string
  gravedad?: string
}

interface IncidenteApi {
  id: string
  vessel: string
  vesselCode: string
  infraction: string
  dateTime: string
  severity: Incident['severity']
  estado: 'sospechoso' | 'confirmado' | 'descartado'
  lat: number | null
  lon: number | null
}

function formatearFecha(iso: string): string {
  const fecha = new Date(iso)
  const dia = fecha.toLocaleDateString('es-PE', { day: '2-digit', month: 'short', timeZone: 'America/Lima' })
  const hora = fecha.toLocaleTimeString('es-PE', { hour: '2-digit', minute: '2-digit', timeZone: 'America/Lima' })
  return `${dia}, ${hora}`
}

/** Incidentes reales registrados en la base de datos (tabla "incidentes"),
 * opcionalmente filtrados por fecha / tipo de embarcación / gravedad. */
export function useIncidentes(filtros: FiltrosIncidentes = {}) {
  const [incidents, setIncidents] = useState<Incident[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const { desde, hasta, tipo, gravedad } = filtros

  const cargar = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const params = new URLSearchParams()
      if (desde) params.set('desde', desde)
      if (hasta) params.set('hasta', hasta)
      if (tipo) params.set('tipo', tipo)
      if (gravedad) params.set('gravedad', gravedad)
      const query = params.toString()

      const response = await apiFetch(`/api/incidentes${query ? `?${query}` : ''}`)
      if (!response.ok) {
        const body = (await response.json().catch(() => null)) as { error?: string } | null
        throw new Error(body?.error ?? `Error ${response.status} al listar incidentes`)
      }
      const data = (await response.json()) as IncidenteApi[]
      setIncidents(data.map((i) => ({ ...i, dateTimeIso: i.dateTime, dateTime: formatearFecha(i.dateTime) })))
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error desconocido')
    } finally {
      setLoading(false)
    }
  }, [desde, hasta, tipo, gravedad])

  useEffect(() => {
    let ignore = false
    void (async () => {
      await cargar()
      if (ignore) return
    })()
    return () => {
      ignore = true
    }
  }, [cargar])

  async function descartar(id: string): Promise<void> {
    const response = await apiFetch(`/api/incidentes/${id}/descartar`, { method: 'POST' })
    if (!response.ok) {
      const body = (await response.json().catch(() => null)) as { error?: string } | null
      throw new Error(body?.error ?? `Error ${response.status} al descartar el incidente`)
    }
    setIncidents((prev) => prev.filter((i) => i.id !== id))
  }

  return { incidents, loading, error, descartar }
}
