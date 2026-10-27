import { DashboardLayout } from '../../../components/layout/DashboardLayout'
import { Badge } from '../../../components/ui/Badge'
import { useAuditoria, type RegistroAuditoria } from '../hooks/useAuditoria'

const ETIQUETA_ACCION: Record<string, { label: string; variant: 'green' | 'amber' | 'gray' | 'red' }> = {
  incidente_registrado: { label: 'Incidente registrado', variant: 'gray' },
  incidente_confirmado: { label: 'Incidente confirmado', variant: 'green' },
  incidente_descartado: { label: 'Incidente descartado', variant: 'red' },
  zona_creada: { label: 'Zona creada', variant: 'gray' },
  zona_eliminada: { label: 'Zona eliminada', variant: 'red' },
  sugerencia_aprobada: { label: 'Sugerencia aprobada', variant: 'green' },
  sugerencia_rechazada: { label: 'Sugerencia rechazada', variant: 'red' },
  fuente_analisis_iniciado: { label: 'Análisis de noticia iniciado', variant: 'gray' },
  usuario_creado: { label: 'Usuario creado', variant: 'gray' },
  usuario_password_cambiada: { label: 'Contraseña cambiada', variant: 'amber' },
  usuario_deshabilitado: { label: 'Usuario deshabilitado', variant: 'red' },
  usuario_habilitado: { label: 'Usuario habilitado', variant: 'green' },
}

function formatearFecha(iso: string): string {
  return new Date(iso).toLocaleString('es-PE', { dateStyle: 'medium', timeStyle: 'short' })
}

function resumenDetalle(registro: RegistroAuditoria): string {
  if (!registro.detalle) return '—'
  return Object.entries(registro.detalle)
    .map(([clave, valor]) => `${clave}: ${valor}`)
    .join(' · ')
}

export function AuditLogPage() {
  const { registros, loading, error } = useAuditoria()

  return (
    <DashboardLayout title="Sistema de Detección de Pesca Ilegal">
      <div className="h-full overflow-y-auto p-6">
        <div>
          <h1 className="text-2xl font-semibold text-slate-900">Auditoría</h1>
          <p className="mt-1 text-sm text-slate-500">
            Quién confirmó o descartó un incidente, creó o eliminó una zona, o aprobó o rechazó una sugerencia
            de la IA, y cuándo. Solo visible para administradores.
          </p>
        </div>

        <div className="mt-6 overflow-x-auto rounded-xl border border-slate-200 bg-white">
          {loading && <p className="p-4 text-sm text-slate-500">Cargando…</p>}
          {error && <p className="p-4 text-sm text-red-600">{error}</p>}
          {!loading && !error && registros.length === 0 && (
            <p className="p-4 text-sm text-slate-500">Todavía no hay acciones registradas.</p>
          )}

          {!loading && !error && registros.length > 0 && (
            <table className="w-full text-left text-sm">
              <thead>
                <tr className="border-b border-slate-200 text-[11px] font-semibold tracking-wide text-slate-400 uppercase">
                  <th className="px-4 py-3">Fecha</th>
                  <th className="px-4 py-3">Usuario</th>
                  <th className="px-4 py-3">Acción</th>
                  <th className="px-4 py-3">Entidad</th>
                  <th className="px-4 py-3">Detalle</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {registros.map((registro) => {
                  const etiqueta = ETIQUETA_ACCION[registro.accion] ?? { label: registro.accion, variant: 'gray' as const }
                  return (
                    <tr key={registro.id} className="hover:bg-slate-50">
                      <td className="px-4 py-3 whitespace-nowrap text-slate-500">{formatearFecha(registro.creado_en)}</td>
                      <td className="px-4 py-3 font-medium text-slate-800">{registro.usuario_nombre ?? 'Desconocido'}</td>
                      <td className="px-4 py-3">
                        <Badge variant={etiqueta.variant}>{etiqueta.label}</Badge>
                      </td>
                      <td className="px-4 py-3 text-slate-600">
                        {registro.entidad}
                        {registro.entidad_id ? ` · ${registro.entidad_id}` : ''}
                      </td>
                      <td className="max-w-md truncate px-4 py-3 text-slate-500">{resumenDetalle(registro)}</td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </DashboardLayout>
  )
}
