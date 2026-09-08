import { useEffect, useState, type FormEvent } from 'react'
import { Button } from '../../../components/ui/Button'
import { SelectField } from '../../../components/ui/SelectField'
import { TextField } from '../../../components/ui/TextField'
import {
  AlertTriangleIcon,
  CalendarIcon,
  LoaderIcon,
  MapPinIcon,
  SearchIcon,
  ShieldCheckIcon,
  ShipIcon,
  XIcon,
} from '../../../components/icons'
import { useBuscarEmbarcacion, type EmbarcacionEncontrada } from '../hooks/useBuscarEmbarcacion'
import { useReportarIncidente } from '../hooks/useReportarIncidente'
import { useTiposInfraccion } from '../hooks/useTiposInfraccion'

function formatearCoordenada(valor: number, positivo: string, negativo: string) {
  const abs = Math.abs(valor)
  const grados = Math.floor(abs)
  const minutos = ((abs - grados) * 60).toFixed(0).padStart(2, '0')
  return `${grados}°${minutos}'00" ${valor >= 0 ? positivo : negativo}`
}

const hoyISO = new Date().toISOString().slice(0, 10)

export interface DatosInicialesIncidente {
  vessel?: string
  mmsi?: string
  descripcion?: string
  lat?: number
  lon?: number
  flag?: string | null
  /** Nombre del tipo de infracción (tal como está en el catálogo) a
   * preseleccionar apenas cargue -- el analista igual puede cambiarlo. */
  tipoInfraccionNombre?: string
}

export function ReportarIncidenteModal({
  onClose,
  onRegistrado,
  datosIniciales,
}: {
  onClose: () => void
  onRegistrado?: () => void
  /** Cuando se abre desde una alerta del mapa (AlertCard): trae los datos ya
   * conocidos de la alerta para no tener que volver a escribirlos ni buscar
   * la ubicación de nuevo -- el analista los revisa/edita antes de enviar,
   * nada se envía automáticamente. */
  datosIniciales?: DatosInicialesIncidente
}) {
  const { tipos, loading: cargandoTipos, error: errorTipos } = useTiposInfraccion()
  const { reportar, enviando, error } = useReportarIncidente()
  const { buscar, buscando, error: errorBusqueda } = useBuscarEmbarcacion()

  const [tipoInfraccionId, setTipoInfraccionId] = useState('')
  const [descripcion, setDescripcion] = useState(datosIniciales?.descripcion ?? '')
  const [gravedad, setGravedad] = useState<'alto' | 'medio' | 'bajo' | ''>('')
  const [vessel, setVessel] = useState(datosIniciales?.vessel ?? '')
  const [mmsi, setMmsi] = useState(datosIniciales?.mmsi ?? '')
  const [fecha, setFecha] = useState(hoyISO)
  const [codigoRegistrado, setCodigoRegistrado] = useState<string | null>(null)
  const [errorIdentidad, setErrorIdentidad] = useState<string | null>(null)
  const [ubicacion, setUbicacion] = useState<EmbarcacionEncontrada | null>(
    datosIniciales?.lat != null && datosIniciales?.lon != null
      ? {
          nombre: datosIniciales.vessel ?? null,
          mmsi: datosIniciales.mmsi ?? null,
          flag: datosIniciales.flag ?? null,
          vesselType: null,
          tipo: 'otro',
          lat: datosIniciales.lat,
          lon: datosIniciales.lon,
        }
      : null,
  )
  const [busquedaHecha, setBusquedaHecha] = useState(datosIniciales?.lat != null && datosIniciales?.lon != null)

  // Preselecciona el tipo de infracción sugerido por la alerta apenas carga
  // el catálogo (no se puede hacer antes: todavía no existen los ids).
  useEffect(() => {
    if (!datosIniciales?.tipoInfraccionNombre || tipoInfraccionId) return
    const sugerido = tipos.find((t) => t.nombre === datosIniciales.tipoInfraccionNombre)
    if (sugerido) {
      setTipoInfraccionId(sugerido.id)
      setGravedad(sugerido.gravedad_sugerida)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tipos])

  function handleTipoChange(id: string) {
    setTipoInfraccionId(id)
    const tipo = tipos.find((t) => t.id === id)
    if (tipo) setGravedad(tipo.gravedad_sugerida)
  }

  // Invalida un resultado de búsqueda anterior si el analista sigue editando
  // el mmsi/nombre después de haber buscado, para no enviar una ubicación
  // que ya no corresponde a lo que escribió.
  function handleVesselChange(valor: string) {
    setVessel(valor)
    setUbicacion(null)
    setBusquedaHecha(false)
  }

  function handleMmsiChange(valor: string) {
    setMmsi(valor)
    setUbicacion(null)
    setBusquedaHecha(false)
  }

  async function handleBuscar() {
    if (!vessel.trim() && !mmsi.trim()) {
      setErrorIdentidad('Ingresa el nombre de la embarcación o su MMSI para poder buscarla')
      return
    }
    setErrorIdentidad(null)
    const encontrada = await buscar({ mmsi: mmsi.trim() || undefined, nombre: vessel.trim() || undefined })
    setUbicacion(encontrada)
    setBusquedaHecha(true)
    if (encontrada) {
      if (!vessel.trim() && encontrada.nombre) setVessel(encontrada.nombre)
      if (!mmsi.trim() && encontrada.mmsi) setMmsi(encontrada.mmsi)
    }
  }

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    if (!vessel.trim() && !mmsi.trim()) {
      setErrorIdentidad('Ingresa el nombre de la embarcación o su MMSI')
      return
    }
    setErrorIdentidad(null)
    const codigo = await reportar({
      tipoInfraccionId,
      descripcion,
      gravedad: gravedad || undefined,
      mmsi: mmsi.trim() || undefined,
      vessel: vessel.trim() || undefined,
      fecha,
      lat: ubicacion?.lat,
      lon: ubicacion?.lon,
      bandera: ubicacion?.flag ?? undefined,
      vesselType: ubicacion?.vesselType ?? undefined,
    })
    if (codigo) {
      setCodigoRegistrado(codigo)
      onRegistrado?.()
    }
  }

  return (
    <div className="fixed inset-0 z-[2000] flex items-center justify-center bg-slate-900/40 p-4" onClick={onClose} role="presentation">
      <div
        className="w-full max-w-md rounded-xl border border-slate-200 bg-white shadow-lg"
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-labelledby="reportar-incidente-title"
      >
        <div className="flex items-center justify-between border-b border-slate-200 px-5 py-3.5">
          <h2 id="reportar-incidente-title" className="flex items-center gap-2 text-sm font-semibold text-slate-900">
            <AlertTriangleIcon className="h-4 w-4 text-red-700" />
            Reportar Incidencia
          </h2>
          <button onClick={onClose} aria-label="Cerrar" className="text-slate-400 hover:text-slate-600">
            <XIcon className="h-4 w-4" />
          </button>
        </div>

        {codigoRegistrado ? (
          <div className="flex flex-col items-center gap-3 px-5 py-8 text-center">
            <ShieldCheckIcon className="h-10 w-10 text-emerald-600" />
            <p className="text-sm font-medium text-slate-800">Incidente {codigoRegistrado} registrado correctamente.</p>
            <p className="text-xs text-slate-500">Ya puedes verlo en Registro de Incidentes.</p>
            <Button type="button" onClick={onClose} className="mt-2 w-auto px-6">
              Cerrar
            </Button>
          </div>
        ) : (
          <form onSubmit={(e) => void handleSubmit(e)} className="flex flex-col gap-4 px-5 py-4">
            <p className="text-xs text-slate-500">
              {datosIniciales
                ? 'Se completaron los datos ya detectados en la alerta -- revísalos y confirma el tipo de infracción antes de registrar.'
                : 'Para reportar algo que no viene de una alerta automática del mapa: una llamada, una denuncia ciudadana, una inspección en puerto, etc.'}
            </p>

            {errorTipos && <p className="text-sm text-red-600">No se pudo cargar el catálogo: {errorTipos}</p>}

            <SelectField
              label="Tipo de infracción"
              value={tipoInfraccionId}
              onChange={(e) => handleTipoChange(e.target.value)}
              required
              disabled={cargandoTipos}
            >
              <option value="" disabled>
                {cargandoTipos ? 'Cargando…' : 'Seleccione un tipo'}
              </option>
              {tipos.map((tipo) => (
                <option key={tipo.id} value={tipo.id}>
                  {tipo.nombre}
                </option>
              ))}
            </SelectField>

            <div className="flex flex-col gap-2">
              <label htmlFor="reportar-descripcion" className="text-xs font-semibold tracking-wide text-slate-500 uppercase">
                Descripción
              </label>
              <textarea
                id="reportar-descripcion"
                rows={3}
                required
                value={descripcion}
                onChange={(e) => setDescripcion(e.target.value)}
                placeholder="Qué se observó, dónde, y la fuente de la información..."
                className="w-full resize-none rounded-lg border border-slate-300 bg-slate-50 p-3 text-sm text-slate-700 placeholder:text-slate-400 focus:border-slate-400 focus:outline-none focus:ring-1 focus:ring-slate-400"
              />
            </div>

            <div className="grid grid-cols-2 gap-3">
              <SelectField label="Gravedad" value={gravedad} onChange={(e) => setGravedad(e.target.value as typeof gravedad)}>
                <option value="alto">Alto</option>
                <option value="medio">Medio</option>
                <option value="bajo">Bajo</option>
              </SelectField>
              <TextField
                id="reportar-fecha"
                label="Fecha"
                type="date"
                icon={<CalendarIcon className="h-4 w-4" />}
                value={fecha}
                onChange={(e) => setFecha(e.target.value)}
                max={hoyISO}
              />
            </div>

            <div className="flex flex-col gap-2">
              <div className="grid grid-cols-2 gap-3">
                <TextField
                  id="reportar-vessel"
                  label="Embarcación"
                  icon={<ShipIcon className="h-4 w-4" />}
                  value={vessel}
                  onChange={(e) => handleVesselChange(e.target.value)}
                  placeholder="Nombre"
                />
                <TextField
                  id="reportar-mmsi"
                  label="MMSI"
                  icon={<ShipIcon className="h-4 w-4" />}
                  value={mmsi}
                  onChange={(e) => handleMmsiChange(e.target.value)}
                  placeholder="9 dígitos"
                />
              </div>
              <p className="text-[11px] text-slate-400">Ingresa al menos uno de los dos.</p>

              <button
                type="button"
                onClick={() => void handleBuscar()}
                disabled={buscando || (!vessel.trim() && !mmsi.trim())}
                className="flex w-full items-center justify-center gap-1.5 rounded-lg border border-slate-300 px-3 py-2 text-xs font-semibold tracking-wide text-slate-600 uppercase hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50"
              >
                {buscando ? (
                  <LoaderIcon className="h-3.5 w-3.5 animate-spin" />
                ) : (
                  <SearchIcon className="h-3.5 w-3.5" />
                )}
                Buscar en GFW
              </button>

              {errorIdentidad && <p className="text-sm text-red-600">{errorIdentidad}</p>}
              {errorBusqueda && <p className="text-sm text-red-600">No se pudo buscar: {errorBusqueda}</p>}

              {busquedaHecha && !buscando && (
                <div className="rounded-lg bg-slate-50 p-2.5 text-xs text-slate-600">
                  {ubicacion ? (
                    <div className="flex items-start gap-2">
                      <MapPinIcon className="mt-0.5 h-3.5 w-3.5 shrink-0 text-emerald-600" />
                      <div>
                        <p className="font-medium text-slate-700">
                          {formatearCoordenada(ubicacion.lat, 'N', 'S')}, {formatearCoordenada(ubicacion.lon, 'E', 'O')}
                        </p>
                        <p className="text-slate-500">
                          {ubicacion.flag ? `Bandera: ${ubicacion.flag}` : 'Bandera desconocida'}
                          {ubicacion.vesselType ? ` · Tipo GFW: ${ubicacion.vesselType}` : ''}
                        </p>
                      </div>
                    </div>
                  ) : (
                    <p>
                      No se encontró en los datos de GFW para el rango de referencia. Puedes continuar el registro sin
                      ubicación detectada.
                    </p>
                  )}
                </div>
              )}
            </div>

            {error && <p className="text-sm text-red-600">{error}</p>}

            <Button type="submit" disabled={enviando || !tipoInfraccionId || (!vessel.trim() && !mmsi.trim())}>
              {enviando ? 'Registrando…' : 'Registrar incidente'}
            </Button>
          </form>
        )}
      </div>
    </div>
  )
}
