import { useEffect, useState } from 'react'
import { apiFetch } from '../../../lib/api'

/** Conjunto de MMSI con al menos un incidente confirmado (para resaltarlos en el mapa). */
export function useMmsiConIncidente() {
  const [mmsiConIncidente, setMmsiConIncidente] = useState<Set<string>>(new Set())

  useEffect(() => {
    let ignore = false

    apiFetch('/api/incidentes/mmsi-con-incidente')
      .then((response) => (response.ok ? (response.json() as Promise<string[]>) : Promise.resolve([])))
      .then((mmsis) => {
        if (!ignore) setMmsiConIncidente(new Set(mmsis))
      })
      .catch(() => {
        // silencioso: si falla, simplemente no se resalta ninguna embarcación
      })

    return () => {
      ignore = true
    }
  }, [])

  return mmsiConIncidente
}
