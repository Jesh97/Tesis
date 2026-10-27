import { useState, type FormEvent } from 'react'
import { DashboardLayout } from '../../../components/layout/DashboardLayout'
import { Badge } from '../../../components/ui/Badge'
import { Button } from '../../../components/ui/Button'
import { SelectField } from '../../../components/ui/SelectField'
import { TextField } from '../../../components/ui/TextField'
import { LockIcon, ShieldCheckIcon, UserIcon } from '../../../components/icons'
import { CambiarPasswordModal } from '../components/CambiarPasswordModal'
import { LONGITUD_MINIMA_PASSWORD, useUsuarios, type RolAsignable, type Usuario } from '../hooks/useUsuarios'

const ETIQUETA_ROL: Record<Usuario['rol'], { label: string; variant: 'green' | 'amber' | 'gray' | 'red' }> = {
  administrador: { label: 'Administrador', variant: 'red' },
  supervisor: { label: 'Supervisor', variant: 'amber' },
  analista: { label: 'Analista', variant: 'gray' },
}

function formatearFecha(iso: string | null): string {
  if (!iso) return 'Nunca'
  return new Date(iso).toLocaleString('es-PE', { dateStyle: 'medium', timeStyle: 'short' })
}

export function UsersPage() {
  const { usuarios, loading, error, crearUsuario, cambiarPassword, cambiarEstado } = useUsuarios()

  const [usuario, setUsuario] = useState('')
  const [nombreCompleto, setNombreCompleto] = useState('')
  const [password, setPassword] = useState('')
  const [confirmacion, setConfirmacion] = useState('')
  const [rol, setRol] = useState<RolAsignable>('analista')
  const [formError, setFormError] = useState<string | null>(null)
  const [exito, setExito] = useState<string | null>(null)
  const [guardando, setGuardando] = useState(false)
  const [usuarioPassword, setUsuarioPassword] = useState<Usuario | null>(null)
  const [mensajeTabla, setMensajeTabla] = useState<{ tipo: 'exito' | 'error'; texto: string } | null>(null)

  async function handleCambiarEstado(u: Usuario) {
    const accion = u.activo ? 'Deshabilitar' : 'Habilitar'
    const aviso = u.activo ? ' No podrá iniciar sesión hasta que se lo vuelva a habilitar.' : ''
    if (!window.confirm(`¿${accion} al usuario ${u.usuario}?${aviso}`)) return
    setMensajeTabla(null)
    try {
      await cambiarEstado(u.id, !u.activo)
      setMensajeTabla({ tipo: 'exito', texto: `Usuario ${u.usuario} ${u.activo ? 'deshabilitado' : 'habilitado'}.` })
    } catch (err) {
      setMensajeTabla({ tipo: 'error', texto: err instanceof Error ? err.message : 'Error desconocido' })
    }
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setFormError(null)
    setExito(null)

    if (password.length < LONGITUD_MINIMA_PASSWORD) {
      setFormError(`La contraseña debe tener al menos ${LONGITUD_MINIMA_PASSWORD} caracteres`)
      return
    }
    if (password !== confirmacion) {
      setFormError('Las contraseñas no coinciden')
      return
    }

    setGuardando(true)
    try {
      await crearUsuario({ usuario, nombreCompleto, password, rol })
      setExito(`Usuario "${usuario.trim().toLowerCase()}" creado. Ya puede iniciar sesión.`)
      setUsuario('')
      setNombreCompleto('')
      setPassword('')
      setConfirmacion('')
      setRol('analista')
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
          <h1 className="text-2xl font-semibold text-slate-900">Usuarios</h1>
          <p className="mt-1 text-sm text-slate-500">
            Crea cuentas de supervisores y analistas, cambia sus contraseñas o deshabilítalas. Solo visible para administradores.
          </p>
        </div>

        <div className="mt-6 grid grid-cols-1 gap-6 lg:grid-cols-[380px_1fr]">
          <form onSubmit={handleSubmit} className="flex flex-col gap-4 rounded-xl border border-slate-200 bg-white p-5">
            <h2 className="text-sm font-semibold text-slate-900">Nuevo usuario</h2>

            <TextField
              id="usuario-nombre-completo"
              label="Nombre completo"
              icon={<UserIcon className="h-4 w-4" />}
              value={nombreCompleto}
              onChange={(e) => setNombreCompleto(e.target.value)}
              placeholder="Ej: Juan Pérez García"
              required
            />
            <TextField
              id="usuario-usuario"
              label="Usuario institucional"
              icon={<UserIcon className="h-4 w-4" />}
              value={usuario}
              onChange={(e) => setUsuario(e.target.value)}
              placeholder="Ej: j.perez"
              autoComplete="off"
              required
            />
            <SelectField
              id="usuario-rol"
              label="Rol"
              icon={<ShieldCheckIcon className="h-4 w-4" />}
              value={rol}
              onChange={(e) => setRol(e.target.value as RolAsignable)}
            >
              <option value="analista">Analista</option>
              <option value="supervisor">Supervisor</option>
            </SelectField>
            <TextField
              id="usuario-password"
              label="Contraseña inicial"
              type="password"
              icon={<LockIcon className="h-4 w-4" />}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder={`Mínimo ${LONGITUD_MINIMA_PASSWORD} caracteres`}
              autoComplete="new-password"
              required
            />
            <TextField
              id="usuario-confirmacion"
              label="Confirmar contraseña"
              type="password"
              icon={<LockIcon className="h-4 w-4" />}
              value={confirmacion}
              onChange={(e) => setConfirmacion(e.target.value)}
              autoComplete="new-password"
              required
            />

            {formError && <p className="text-sm text-red-600">{formError}</p>}
            {exito && <p className="text-sm text-green-700">{exito}</p>}

            <Button type="submit" disabled={guardando}>
              {guardando ? 'Guardando…' : 'Crear usuario'}
            </Button>
          </form>

          <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white">
            <h2 className="px-5 pt-5 text-sm font-semibold text-slate-900">Usuarios registrados</h2>

            {loading && <p className="p-5 text-sm text-slate-500">Cargando…</p>}
            {error && <p className="p-5 text-sm text-red-600">{error}</p>}
            {mensajeTabla && (
              <p className={`px-5 pt-3 text-sm ${mensajeTabla.tipo === 'exito' ? 'text-green-700' : 'text-red-600'}`}>
                {mensajeTabla.texto}
              </p>
            )}

            {!loading && !error && (
              <table className="mt-3 w-full text-left text-sm">
                <thead>
                  <tr className="border-b border-slate-200 text-[11px] font-semibold tracking-wide text-slate-400 uppercase">
                    <th className="px-5 py-3">Nombre</th>
                    <th className="px-5 py-3">Usuario</th>
                    <th className="px-5 py-3">Rol</th>
                    <th className="px-5 py-3">Estado</th>
                    <th className="px-5 py-3">Último acceso</th>
                    <th className="px-5 py-3">Acciones</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {usuarios.map((u) => (
                    <tr key={u.id}>
                      <td className="px-5 py-3 text-slate-900">{u.nombre_completo}</td>
                      <td className="px-5 py-3 text-slate-600">{u.usuario}</td>
                      <td className="px-5 py-3">
                        <Badge variant={ETIQUETA_ROL[u.rol].variant}>{ETIQUETA_ROL[u.rol].label}</Badge>
                      </td>
                      <td className="px-5 py-3">
                        <Badge variant={u.activo ? 'green' : 'gray'}>{u.activo ? 'Activo' : 'Deshabilitado'}</Badge>
                      </td>
                      <td className="px-5 py-3 text-slate-600">{formatearFecha(u.ultimo_acceso)}</td>
                      <td className="px-5 py-3">
                        {/* Solo cuentas de menor rango: el backend rechaza modificar a un administrador. */}
                        {u.rol !== 'administrador' && (
                          <div className="flex items-center gap-3 text-xs font-medium whitespace-nowrap">
                            <button
                              onClick={() => {
                                setMensajeTabla(null)
                                setUsuarioPassword(u)
                              }}
                              className="text-slate-600 hover:text-slate-900"
                            >
                              Cambiar contraseña
                            </button>
                            <button
                              onClick={() => void handleCambiarEstado(u)}
                              className={u.activo ? 'text-red-600 hover:text-red-800' : 'text-green-700 hover:text-green-900'}
                            >
                              {u.activo ? 'Deshabilitar' : 'Habilitar'}
                            </button>
                          </div>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </div>
      </div>

      {usuarioPassword && (
        <CambiarPasswordModal
          usuario={usuarioPassword}
          onGuardar={async (nueva) => {
            await cambiarPassword(usuarioPassword.id, nueva)
            setMensajeTabla({ tipo: 'exito', texto: `Contraseña de ${usuarioPassword.usuario} actualizada.` })
          }}
          onClose={() => setUsuarioPassword(null)}
        />
      )}
    </DashboardLayout>
  )
}
