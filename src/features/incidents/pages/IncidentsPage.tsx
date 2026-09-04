import { useState } from 'react'
import { DashboardLayout } from '../../../components/layout/DashboardLayout'
import { Pagination } from '../../../components/ui/Pagination'
import { SelectField } from '../../../components/ui/SelectField'
import { TextField } from '../../../components/ui/TextField'
import { CalendarIcon, DownloadIcon } from '../../../components/icons'
import { IncidentsTable } from '../components/IncidentsTable'
import { mockIncidents, totalIncidents } from '../data/mockIncidents'

const pageSize = 4
const pageCount = Math.ceil(totalIncidents / pageSize)

export function IncidentsPage() {
  const [page, setPage] = useState(1)

  return (
    <DashboardLayout title="Sistema de Detección de Pesca Ilegal" searchPlaceholder="Buscar incidente o embarcación...">
      <div className="h-full overflow-y-auto p-6">
        <div className="flex items-start justify-between">
          <div>
            <h1 className="text-2xl font-semibold text-slate-900">Registro de Incidentes</h1>
            <p className="mt-1 text-sm text-slate-500">
              Gestión y seguimiento de infracciones marítimas detectadas en tiempo real.
            </p>
          </div>
          <button className="flex items-center gap-2 rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-medium text-slate-700 shadow-sm hover:bg-slate-50">
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
            />
            <span className="pb-2.5 text-slate-400">-</span>
            <TextField id="date-to" label=" " type="date" icon={<CalendarIcon className="h-4 w-4" />} />
          </div>

          <SelectField label="Tipo de embarcación">
            <option>Todos los tipos</option>
            <option>Pesca artesanal</option>
            <option>Pesca industrial</option>
            <option>Carga</option>
          </SelectField>

          <SelectField label="Gravedad">
            <option>Cualquier nivel</option>
            <option>Alto</option>
            <option>Medio</option>
            <option>Bajo</option>
          </SelectField>

          <button className="ml-auto flex items-center gap-2 rounded-lg bg-slate-900 px-5 py-2.5 text-sm font-semibold text-white hover:bg-slate-800">
            Aplicar
          </button>
        </div>

        <div className="mt-6 overflow-hidden rounded-xl border border-slate-200 bg-white">
          <IncidentsTable incidents={mockIncidents} />
          <div className="border-t border-slate-200">
            <Pagination
              page={page}
              pageCount={pageCount}
              totalItems={totalIncidents}
              pageSize={pageSize}
              onPageChange={setPage}
            />
          </div>
        </div>
      </div>
    </DashboardLayout>
  )
}
