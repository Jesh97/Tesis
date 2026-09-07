import { useState, type FormEvent } from 'react'
import { Button } from '../../../components/ui/Button'
import { SelectField } from '../../../components/ui/SelectField'
import { TextField } from '../../../components/ui/TextField'
import { AlertTriangleIcon, CalendarIcon, ShieldCheckIcon, ShipIcon, XIcon } from '../../../components/icons'
import { useReportarIncidente } from '../hooks/useReportarIncidente'
import { useTiposInfraccion } from '../hooks/useTiposInfraccion'

const hoyISO = new Date().toISOString().slice(0, 10)

export function ReportarIncidenteModal({ onClose }: { onClose: () => void }) {
  const { tipos, loading: cargandoTipos, error: errorTipos } = useTiposInfraccion()
  const { reportar, enviando, error } = useReportarIncidente()

  const [tipoInfraccionId, setTipoInfraccionId] = useState('')
  const [descripcion, setDescripcion] = useState('')
  const [gravedad, setGravedad] = useState<'alto' | 'medio' | 'bajo' | ''>('')
  const [vessel, setVessel] = useState('')
  const [mmsi, setMmsi] = useState('')
  const [fecha, setFecha] = useState(hoyISO)
  const [codigoRegistrado, setCodigoRegistrado] = useState<string | null>(null)

  function handleTipoChange(id: string) {
    setTipoInfraccionId(id)
    const tipo = tipos.find((t) => t.id === id)
    if (tipo) setGravedad(tipo.gravedad_sugerida)
  }

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    const codigo = await reportar({
      tipoInfraccionId,
      descripcion,
      gravedad: gravedad || undefined,
      mmsi: mmsi.trim() || undefined,
      vessel: vessel.trim() || undefined,
      fecha,
    })
    if (codigo) setCodigoRegistrado(codigo)
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
              Para reportar algo que no viene de una alerta automática del mapa: una llamada, una denuncia ciudadana, una
              inspección en puerto, etc.
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

            <div className="grid grid-cols-2 gap-3">
              <TextField
                id="reportar-vessel"
                label="Embarcación (opcional)"
                icon={<ShipIcon className="h-4 w-4" />}
                value={vessel}
                onChange={(e) => setVessel(e.target.value)}
                placeholder="Nombre"
              />
              <TextField
                id="reportar-mmsi"
                label="MMSI (opcional)"
                icon={<ShipIcon className="h-4 w-4" />}
                value={mmsi}
                onChange={(e) => setMmsi(e.target.value)}
                placeholder="9 dígitos"
              />
            </div>

            {error && <p className="text-sm text-red-600">{error}</p>}

            <Button type="submit" disabled={enviando || !tipoInfraccionId}>
              {enviando ? 'Registrando…' : 'Registrar incidente'}
            </Button>
          </form>
        )}
      </div>
    </div>
  )
}
