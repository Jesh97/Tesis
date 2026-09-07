import { cerrarSesion, obtenerSesion } from './session'

/** Wrapper de fetch que adjunta el token de sesión y limpia la sesión + manda
 * a login si el backend responde 401 (token ausente/expirado). Todos los
 * hooks que llaman a /api/* (menos /api/auth/login) deben usar este helper
 * en vez de fetch directo. */
export async function apiFetch(path: string, options: RequestInit = {}): Promise<Response> {
  const sesion = obtenerSesion()
  const headers = new Headers(options.headers)
  if (sesion) headers.set('Authorization', `Bearer ${sesion.token}`)

  const response = await fetch(path, { ...options, headers })

  if (response.status === 401) {
    cerrarSesion()
    if (window.location.pathname !== '/') {
      window.location.href = '/'
    }
  }

  return response
}
