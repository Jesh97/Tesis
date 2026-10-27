import { useState, type FormEvent } from 'react'
import { Button } from '../../../components/ui/Button'
import { TextField } from '../../../components/ui/TextField'
import { LockIcon, XIcon } from '../../../components/icons'
import { LONGITUD_MINIMA_PASSWORD, type Usuario } from '../hooks/useUsuarios'

interface CambiarPasswordModalProps {
  usuario: Usuario
  onGuardar: (password: string) => Promise<void>
  onClose: () => void
}

export function CambiarPasswordModal({ usuario, onGuardar, onClose }: CambiarPasswordModalProps) {
  const [password, setPassword] = useState('')
  const [confirmacion, setConfirmacion] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [guardando, setGuardando] = useState(false)

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setError(null)
    if (password.length < LONGITUD_MINIMA_PASSWORD) {
      setError(`La contraseña debe tener al menos ${LONGITUD_MINIMA_PASSWORD} caracteres`)
      return
    }
    if (password !== confirmacion) {
      setError('Las contraseñas no coinciden')
      return
    }
    setGuardando(true)
    try {
      await onGuardar(password)
      onClose()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error desconocido')
      setGuardando(false)
    }
  }

  return (
    <div className="fixed inset-0 z-[2000] flex items-center justify-center bg-slate-900/40 p-4">
      <form
        onSubmit={handleSubmit}
        className="flex w-full max-w-sm flex-col gap-4 rounded-xl border border-slate-200 bg-white p-5 shadow-lg"
      >
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-semibold text-slate-900">Cambiar contraseña</h2>
          <button type="button" onClick={onClose} aria-label="Cerrar" className="text-slate-400 hover:text-slate-600">
            <XIcon className="h-4 w-4" />
          </button>
        </div>
        <p className="text-sm text-slate-500">
          Nueva contraseña para <span className="font-medium text-slate-800">{usuario.nombre_completo}</span> (
          {usuario.usuario}). Comunícasela al usuario por un canal seguro.
        </p>

        <TextField
          id="cambiar-password"
          label="Nueva contraseña"
          type="password"
          icon={<LockIcon className="h-4 w-4" />}
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          placeholder={`Mínimo ${LONGITUD_MINIMA_PASSWORD} caracteres`}
          autoComplete="new-password"
          autoFocus
          required
        />
        <TextField
          id="cambiar-password-confirmacion"
          label="Confirmar contraseña"
          type="password"
          icon={<LockIcon className="h-4 w-4" />}
          value={confirmacion}
          onChange={(e) => setConfirmacion(e.target.value)}
          autoComplete="new-password"
          required
        />

        {error && <p className="text-sm text-red-600">{error}</p>}

        <Button type="submit" disabled={guardando}>
          {guardando ? 'Guardando…' : 'Guardar contraseña'}
        </Button>
      </form>
    </div>
  )
}
