import { useMemo, useState } from 'react'
import { DashboardLayout } from '../../../components/layout/DashboardLayout'
import { Pagination } from '../../../components/ui/Pagination'
import { SelectField } from '../../../components/ui/SelectField'
import { TextField } from '../../../components/ui/TextField'
import { CalendarIcon, DownloadIcon } from '../../../components/icons'
import { descargarCSV } from '../../../lib/csv'
import { IncidentsTable } from '../components/IncidentsTable'
import { useIncidentes, type FiltrosIncidentes } from '../hooks/useIncidentes'

const pageSize = 4
const FILTROS_VACIOS: FiltrosIncidentes = {}

export function IncidentsPage() {
  const [page, setPage] = useState(1)
  const [borrador, setBorrador] = useState<FiltrosIncidentes>(FILTROS_VACIOS)
  const [filtrosAplicados, setFiltrosAplicados] = useState<FiltrosIncidentes>(FILTROS_VACIOS)
  const { incidents, loading, error, descartar } = useIncidentes(filtrosAplicados)

  const hayFiltrosActivos = Object.values(filtrosAplicados).some((v) => v)

  const pageCount = Math.max(1, Math.ceil(incidents.length / pageSize))
  const pageItems = useMemo(
    () => incidents.slice((page - 1) * pageSize, page * pageSize),
    [incidents, page],
  )

  function aplicarFiltros() {
    setFiltrosAplicados(borrador)
    setPage(1)
  }

  function limpiarFiltros() {
    setBorrador(FILTROS_VACIOS)
    setFiltrosAplicados(FILTROS_VACIOS)
    setPage(1)
  }

  function exportarCSV() {
    const encabezado = ['ID Incidente', 'Embarcación', 'Identificador', 'Tipo de Infracción', 'Fecha y Hora', 'Gravedad']
    const filas = incidents.map((i) => [i.id, i.vessel, i.vesselCode, i.infraction, i.dateTimeIso, i.severity])
    const fecha = new Date().toISOString().slice(0, 10)
    descargarCSV(`incidentes_${fecha}.csv`, [encabezado, ...filas])
  }

  return (
    <DashboardLayout title="Sistema de Detección de Pesca Ilegal" searchPlaceholder="Buscar incidente o embarcación...">
      <div className="h-full overflow-y-auto p-6">
        <div className="flex items-start justify-between">
          <div>
            <h1 className="text-2xl font-semibold text-slate-900">Registro de Incidentes</h1>
            <p className="mt-1 text-sm text-slate-500">
              Gestión y seguimiento de infracciones marítimas registradas a partir de datos satelitales.
            </p>
          </div>
          <button
            onClick={exportarCSV}
            disabled={incidents.length === 0}
            className="flex items-center gap-2 rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-medium text-slate-700 shadow-sm hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50"
          >
            <DownloadIcon className="h-4 w-4" />
            Exportar CSV
          </button>
        </div>

        <div className="mt-6 flex flex-wrap items-end gap-4 rounded-xl border border-slate-200 bg-white p-4">
          <div className="flex items-end gap-2">
            <TextField
              id="date-from"
              label="Fecha de detección"
              type="date"
              icon={<CalendarIcon className="h-4 w-4" />}
              value={borrador.desde ?? ''}
              onChange={(e) => setBorrador((prev) => ({ ...prev, desde: e.target.value || undefined }))}
            />
            <span className="pb-2.5 text-slate-400">-</span>
            <TextField
              id="date-to"
              label=" "
              type="date"
              icon={<CalendarIcon className="h-4 w-4" />}
              value={borrador.hasta ?? ''}
              onChange={(e) => setBorrador((prev) => ({ ...prev, hasta: e.target.value || undefined }))}
            />
          </div>

          <SelectField
            label="Tipo de embarcación"
            value={borrador.tipo ?? ''}
            onChange={(e) => setBorrador((prev) => ({ ...prev, tipo: e.target.value || undefined }))}
          >
            <option value="">Todos los tipos</option>
            <option value="pesca_artesanal">Pesca artesanal</option>
            <option value="pesca_industrial">Pesca industrial</option>
            <option value="carga">Carga</option>
          </SelectField>

          <SelectField
            label="Gravedad"
            value={borrador.gravedad ?? ''}
            onChange={(e) => setBorrador((prev) => ({ ...prev, gravedad: e.target.value || undefined }))}
          >
            <option value="">Cualquier nivel</option>
            <option value="alto">Alto</option>
            <option value="medio">Medio</option>
            <option value="bajo">Bajo</option>
          </SelectField>

          {hayFiltrosActivos && (
            <button onClick={limpiarFiltros} className="text-sm font-medium text-slate-500 hover:text-slate-700">
              Limpiar filtros
            </button>
          )}
          <button
            onClick={aplicarFiltros}
            className="ml-auto flex items-center gap-2 rounded-lg bg-slate-900 px-5 py-2.5 text-sm font-semibold text-white hover:bg-slate-800"
          >
            Aplicar
          </button>
        </div>

        <div className="mt-6 overflow-hidden rounded-xl border border-slate-200 bg-white">
          {error && <p className="p-4 text-sm text-red-600">No se pudieron cargar los incidentes: {error}</p>}
          {!error && loading && <p className="p-4 text-sm text-slate-500">Cargando…</p>}
          {!error && !loading && incidents.length === 0 && (
            <p className="p-4 text-sm text-slate-500">
              {hayFiltrosActivos ? 'Ningún incidente coincide con los filtros aplicados.' : 'Todavía no hay incidentes registrados.'}
            </p>
          )}
          {!error && incidents.length > 0 && (
            <>
              <IncidentsTable incidents={pageItems} onDescartar={descartar} />
              <div className="border-t border-slate-200">
                <Pagination
                  page={page}
                  pageCount={pageCount}
                  totalItems={incidents.length}
                  pageSize={pageSize}
                  onPageChange={setPage}
                />
              </div>
            </>
          )}
        </div>
      </div>
    </DashboardLayout>
  )
}
