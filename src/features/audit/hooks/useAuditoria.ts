import { useEffect, useState } from 'react'
import { apiFetch } from '../../../lib/api'

export interface RegistroAuditoria {
  id: string
  usuario_id: string | null
  usuario_nombre: string | null
  accion: string
  entidad: string
  entidad_id: string | null
  detalle: Record<string, unknown> | null
  creado_en: string
}

/** GET /api/auditoria (solo administrador, ver server/app/routes/auditoria.py):
 * quién confirmó/descartó un incidente, creó/eliminó una zona o aprobó/rechazó
 * una sugerencia, y cuándo. */
export function useAuditoria() {
  const [registros, setRegistros] = useState<RegistroAuditoria[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let ignore = false

    async function cargar() {
      setLoading(true)
      setError(null)
      try {
        const response = await apiFetch('/api/auditoria')
        if (!response.ok) {
          const body = (await response.json().catch(() => null)) as { error?: string } | null
          throw new Error(body?.error ?? `Error ${response.status} al cargar la auditoría`)
        }
        const datos = (await response.json()) as RegistroAuditoria[]
        if (!ignore) setRegistros(datos)
      } catch (err) {
        if (!ignore) setError(err instanceof Error ? err.message : 'Error desconocido')
      } finally {
        if (!ignore) setLoading(false)
      }
    }

    void cargar()
    return () => {
      ignore = true
    }
  }, [])

  return { registros, loading, error }
}
