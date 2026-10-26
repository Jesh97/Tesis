import { useEffect, useState } from 'react'
import { apiFetch } from '../../../lib/api'
import type { LambayequeVessel } from '../../monitoring/hooks/useLambayequeVessels'

/** Barco de /api/actividad/historico: misma forma que el mapa de monitoreo
 * (ver barcos_del_mes en server/app/actividad_mensual.py). */
export interface BarcoHistorico extends LambayequeVessel {
  horasPresencia: number
  pescando: boolean
}

interface RespuestaHistorico {
  mes: string
  parcial: boolean
  total: number
  pescando: number
  barcos: BarcoHistorico[]
}

/** Embarcaciones vistas en la jurisdicción de Lambayeque en un mes puntual.
 * Mantiene los barcos del mes anterior en pantalla mientras carga el nuevo
 * (en vez de vaciar el mapa), para que la reproducción mes a mes no parpadee. */
export function useHistoricoMes(mes: string) {
  const [barcos, setBarcos] = useState<BarcoHistorico[]>([])
  const [mesCargado, setMesCargado] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let ignore = false

    async function load() {
      setLoading(true)
      setError(null)
      try {
        const response = await apiFetch(`/api/actividad/historico?mes=${encodeURIComponent(mes)}`)
        const data = await response.json()
        if (!response.ok) throw new Error(data?.error ?? `Error ${response.status} al consultar GFW`)
        if (!ignore) {
          setBarcos((data as RespuestaHistorico).barcos)
          setMesCargado(mes)
        }
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
  }, [mes])

  return { barcos, mesCargado, loading, error }
}
