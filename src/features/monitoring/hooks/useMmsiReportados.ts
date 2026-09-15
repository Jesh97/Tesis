import { useEffect, useState } from 'react'
import { apiFetch } from '../../../lib/api'

/** Conjunto de MMSI con al menos un incidente activo (no descartado), para no
 * volver a mostrar (ni permitir re-registrar) una alerta ya reportada. */
export function useMmsiReportados() {
  const [mmsiReportados, setMmsiReportados] = useState<Set<string>>(new Set())

  useEffect(() => {
    let ignore = false

    apiFetch('/api/incidentes/mmsi-reportados')
      .then((response) => (response.ok ? (response.json() as Promise<string[]>) : Promise.resolve([])))
      .then((mmsis) => {
        if (!ignore) setMmsiReportados(new Set(mmsis))
      })
      .catch(() => {
        // silencioso: si falla, simplemente no se filtra ninguna alerta por este criterio
      })

    return () => {
      ignore = true
    }
  }, [])

  return mmsiReportados
}
