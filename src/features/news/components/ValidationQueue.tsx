import { useState } from 'react'
import { InboxIcon } from '../../../components/icons'
import type { Fuente } from '../hooks/useFuentes'
import { useSugerencias } from '../hooks/useSugerencias'
import { ProcessingRow } from './ProcessingRow'
import { ValidationCard } from './ValidationCard'

export function ValidationQueue({ fuentesEnProceso }: { fuentesEnProceso: Fuente[] }) {
  const { sugerencias, loading, error, aprobar, rechazar } = useSugerencias()
  const [accionId, setAccionId] = useState<string | null>(null)
  const [errorAccion, setErrorAccion] = useState<string | null>(null)
  const pendingCount = sugerencias.length + fuentesEnProceso.length

  async function handleAprobar(id: string) {
    setAccionId(id)
    setErrorAccion(null)
    try {
      await aprobar(id)
    } catch (err) {
      setErrorAccion(err instanceof Error ? err.message : 'Error desconocido')
    } finally {
      setAccionId(null)
    }
  }

  async function handleRechazar(id: string) {
    setAccionId(id)
    setErrorAccion(null)
    try {
      await rechazar(id)
    } catch (err) {
      setErrorAccion(err instanceof Error ? err.message : 'Error desconocido')
    } finally {
      setAccionId(null)
    }
  }

  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2 text-sm font-semibold text-slate-900">
          <InboxIcon className="h-4 w-4" />
          Cola de Validación IA
        </div>
        <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-medium text-slate-600">
          {pendingCount} Pendientes
        </span>
      </div>

      {error && <p className="text-sm text-red-600">No se pudo cargar la cola: {error}</p>}
      {errorAccion && <p className="text-sm text-red-600">{errorAccion}</p>}
      {!loading && !error && pendingCount === 0 && (
        <p className="text-sm text-slate-500">No hay sugerencias pendientes de validación.</p>
      )}

      {sugerencias.map((item) => (
        <ValidationCard
          key={item.id}
          item={item}
          procesando={accionId === item.id}
          onAprobar={() => void handleAprobar(item.id)}
          onRechazar={() => void handleRechazar(item.id)}
        />
      ))}

      {fuentesEnProceso.map((item) => (
        <ProcessingRow key={item.id} item={item} />
      ))}
    </div>
  )
}
