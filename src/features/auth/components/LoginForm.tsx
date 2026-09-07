import { useState, type FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { EyeIcon, EyeOffIcon, LockIcon, LogInIcon, UserIcon } from '../../../components/icons'
import { Button } from '../../../components/ui/Button'
import { Checkbox } from '../../../components/ui/Checkbox'
import { TextField } from '../../../components/ui/TextField'
import { guardarSesion, type Sesion } from '../../../lib/session'

export function LoginForm() {
  const navigate = useNavigate()
  const [showPassword, setShowPassword] = useState(false)
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [rememberMe, setRememberMe] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setError(null)
    setLoading(true)
    try {
      const response = await fetch('/api/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ usuario: username, password }),
      })
      if (!response.ok) {
        const body = (await response.json().catch(() => null)) as { error?: string } | null
        throw new Error(body?.error ?? 'No se pudo iniciar sesión')
      }
      const sesion = (await response.json()) as Sesion
      guardarSesion(sesion, rememberMe)
      navigate('/monitoreo')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error desconocido')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="flex flex-col justify-center p-8 sm:p-14">
      <div className="mx-auto w-full max-w-sm">
        <h2 className="text-2xl font-semibold text-slate-900">Iniciar Sesión</h2>
        <p className="mt-2 text-sm text-slate-500">
          Ingrese sus credenciales institucionales para acceder al panel de
          control.
        </p>

        <form className="mt-8 flex flex-col gap-5" onSubmit={handleSubmit}>
          <TextField
            id="username"
            label="Usuario institucional"
            type="text"
            placeholder="Ej: inicial.apellido"
            icon={<UserIcon className="h-4 w-4" />}
            value={username}
            onChange={(event) => setUsername(event.target.value)}
            autoComplete="username"
            required
          />

          <TextField
            id="password"
            label="Contraseña"
            type={showPassword ? 'text' : 'password'}
            placeholder="••••••••"
            icon={<LockIcon className="h-4 w-4" />}
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            autoComplete="current-password"
            required
            trailingAction={
              <button
                type="button"
                onClick={() => setShowPassword((visible) => !visible)}
                className="text-slate-400 hover:text-slate-600"
                aria-label={
                  showPassword ? 'Ocultar contraseña' : 'Mostrar contraseña'
                }
              >
                {showPassword ? (
                  <EyeOffIcon className="h-4 w-4" />
                ) : (
                  <EyeIcon className="h-4 w-4" />
                )}
              </button>
            }
          />

          <div className="flex items-center justify-between">
            <Checkbox
              id="remember-me"
              label="Recordar sesión"
              checked={rememberMe}
              onChange={(event) => setRememberMe(event.target.checked)}
            />
            <a
              href="#"
              className="text-xs font-medium text-slate-500 underline-offset-2 hover:text-slate-700 hover:underline"
            >
              ¿Olvidó su contraseña?
            </a>
          </div>

          {error && <p className="text-sm text-red-600">{error}</p>}

          <Button type="submit" disabled={loading}>
            {loading ? 'Ingresando…' : 'Ingresar al sistema'}
            <LogInIcon className="h-4 w-4" />
          </Button>
        </form>

        <hr className="mt-8 border-slate-200" />

        <p className="mt-6 text-center text-xs text-slate-400">
          © 2026 Gobierno del Perú.
          <br />
          Uso exclusivo para personal gubernamental autorizado.
        </p>
      </div>
    </div>
  )
}
