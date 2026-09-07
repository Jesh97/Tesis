import { useState, type FormEvent } from 'react'
import { DashboardLayout } from '../../../components/layout/DashboardLayout'
import { Button } from '../../../components/ui/Button'
import { Checkbox } from '../../../components/ui/Checkbox'
import { TextField } from '../../../components/ui/TextField'
import { MapPinIcon, PlusIcon, XIcon } from '../../../components/icons'
import { useZonas, type Coordenada } from '../hooks/useZonas'

const FILA_VACIA = { lat: '', lon: '' }

export function ZonesPage() {
  const { zonas, loading, error, crearZona, eliminarZona } = useZonas()

  const [nombre, setNombre] = useState('')
  const [region, setRegion] = useState('')
  const [esCritica, setEsCritica] = useState(true)
  const [filas, setFilas] = useState([{ ...FILA_VACIA }, { ...FILA_VACIA }, { ...FILA_VACIA }])
  const [formError, setFormError] = useState<string | null>(null)
  const [guardando, setGuardando] = useState(false)

  function actualizarFila(index: number, campo: 'lat' | 'lon', valor: string) {
    setFilas((prev) => prev.map((f, i) => (i === index ? { ...f, [campo]: valor } : f)))
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setFormError(null)

    const coordenadas: Coordenada[] = []
    for (const fila of filas) {
      if (fila.lat.trim() === '' && fila.lon.trim() === '') continue
      const lat = Number(fila.lat)
      const lon = Number(fila.lon)
      if (Number.isNaN(lat) || Number.isNaN(lon)) {
        setFormError('Las coordenadas deben ser números válidos (lat, lon)')
        return
      }
      coordenadas.push({ lat, lon })
    }
    if (coordenadas.length < 3) {
      setFormError('Se necesitan al menos 3 coordenadas para formar un polígono')
      return
    }

    setGuardando(true)
    try {
      await crearZona({ nombre, region, esCritica, coordenadas })
      setNombre('')
      setRegion('')
      setEsCritica(true)
      setFilas([{ ...FILA_VACIA }, { ...FILA_VACIA }, { ...FILA_VACIA }])
    } catch (err) {
      setFormError(err instanceof Error ? err.message : 'Error desconocido')
    } finally {
      setGuardando(false)
    }
  }

  return (
    <DashboardLayout title="Sistema de Detección de Pesca Ilegal">
      <div className="h-full overflow-y-auto p-6">
        <div>
          <h1 className="text-2xl font-semibold text-slate-900">Zonas Protegidas</h1>
          <p className="mt-1 text-sm text-slate-500">
            Define zonas mediante coordenadas para detectar embarcaciones que ingresen a ellas (patrón
            "zona_protegida" de detección de irregularidades).
          </p>
        </div>

        <div className="mt-6 grid grid-cols-1 gap-6 lg:grid-cols-[380px_1fr]">
          <form onSubmit={handleSubmit} className="flex flex-col gap-4 rounded-xl border border-slate-200 bg-white p-5">
            <h2 className="text-sm font-semibold text-slate-900">Nueva zona</h2>

            <TextField
              id="zona-nombre"
              label="Nombre"
              icon={<MapPinIcon className="h-4 w-4" />}
              value={nombre}
              onChange={(e) => setNombre(e.target.value)}
              placeholder="Ej: Reserva artesanal 5mn"
              required
            />
            <TextField
              id="zona-region"
              label="Región"
              icon={<MapPinIcon className="h-4 w-4" />}
              value={region}
              onChange={(e) => setRegion(e.target.value)}
              placeholder="Ej: Lambayeque"
              required
            />
            <Checkbox
              id="zona-critica"
              label="Zona crítica (activa la detección de irregularidades)"
              checked={esCritica}
              onChange={(e) => setEsCritica(e.target.checked)}
            />

            <div>
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold tracking-wide text-slate-500 uppercase">
                  Coordenadas del polígono
                </span>
                <button
                  type="button"
                  onClick={() => setFilas((prev) => [...prev, { ...FILA_VACIA }])}
                  className="flex items-center gap-1 text-xs font-medium text-slate-600 hover:text-slate-900"
                >
                  <PlusIcon className="h-3.5 w-3.5" />
                  Agregar punto
                </button>
              </div>

              <div className="mt-2 flex flex-col gap-2">
                {filas.map((fila, index) => (
                  <div key={index} className="flex items-center gap-2">
                    <input
                      type="number"
                      step="any"
                      placeholder="Latitud"
                      value={fila.lat}
                      onChange={(e) => actualizarFila(index, 'lat', e.target.value)}
                      className="w-full rounded-lg border border-slate-300 bg-slate-50 px-3 py-2 text-sm text-slate-800 placeholder:text-slate-400 focus:outline-none focus:ring-1 focus:ring-slate-400"
                    />
                    <input
                      type="number"
                      step="any"
                      placeholder="Longitud"
                      value={fila.lon}
                      onChange={(e) => actualizarFila(index, 'lon', e.target.value)}
                      className="w-full rounded-lg border border-slate-300 bg-slate-50 px-3 py-2 text-sm text-slate-800 placeholder:text-slate-400 focus:outline-none focus:ring-1 focus:ring-slate-400"
                    />
                    <button
                      type="button"
                      aria-label="Quitar punto"
                      onClick={() => setFilas((prev) => prev.filter((_, i) => i !== index))}
                      disabled={filas.length <= 3}
                      className="shrink-0 text-slate-400 hover:text-red-600 disabled:cursor-not-allowed disabled:opacity-30"
                    >
                      <XIcon className="h-4 w-4" />
                    </button>
                  </div>
                ))}
              </div>
              <p className="mt-1 text-[11px] text-slate-400">
                El polígono se cierra automáticamente uniendo el último punto con el primero.
              </p>
            </div>

            {formError && <p className="text-sm text-red-600">{formError}</p>}

            <Button type="submit" disabled={guardando}>
              {guardando ? 'Guardando…' : 'Crear zona'}
            </Button>
          </form>

          <div className="rounded-xl border border-slate-200 bg-white p-5">
            <h2 className="text-sm font-semibold text-slate-900">Zonas registradas</h2>

            {loading && <p className="mt-3 text-sm text-slate-500">Cargando…</p>}
            {error && <p className="mt-3 text-sm text-red-600">{error}</p>}
            {!loading && zonas.length === 0 && (
              <p className="mt-3 text-sm text-slate-500">Todavía no hay zonas registradas.</p>
            )}

            <ul className="mt-3 flex flex-col gap-2">
              {zonas.map((zona) => (
                <li
                  key={zona.id}
                  className="flex items-center justify-between rounded-lg border border-slate-200 p-3"
                >
                  <div>
                    <p className="text-sm font-medium text-slate-900">
                      {zona.nombre}{' '}
                      {zona.es_critica && (
                        <span className="ml-1 rounded bg-red-100 px-1.5 py-0.5 text-[10px] font-bold tracking-wide text-red-700 uppercase">
                          Crítica
                        </span>
                      )}
                    </p>
                    <p className="text-xs text-slate-500">
                      {zona.region} · {zona.poligono?.coordinates[0]?.length ?? 0} puntos
                    </p>
                  </div>
                  <button
                    onClick={() => void eliminarZona(zona.id)}
                    aria-label="Eliminar zona"
                    className="text-slate-400 hover:text-red-600"
                  >
                    <XIcon className="h-4 w-4" />
                  </button>
                </li>
              ))}
            </ul>
          </div>
        </div>
      </div>
    </DashboardLayout>
  )
}
