export interface Sesion {
  token: string
  id: string
  usuario: string
  nombreCompleto: string
  rol: string
}

const CLAVE = 'pesca_ilegal_sesion'

/** Guarda la sesión en localStorage (si "recordar sesión" está marcado) o
 * sessionStorage (se pierde al cerrar la pestaña) -- nunca en ambos a la vez. */
export function guardarSesion(sesion: Sesion, recordar: boolean): void {
  const destino = recordar ? localStorage : sessionStorage
  const otro = recordar ? sessionStorage : localStorage
  destino.setItem(CLAVE, JSON.stringify(sesion))
  otro.removeItem(CLAVE)
}

export function obtenerSesion(): Sesion | null {
  const cruda = localStorage.getItem(CLAVE) ?? sessionStorage.getItem(CLAVE)
  if (!cruda) return null
  try {
    return JSON.parse(cruda) as Sesion
  } catch {
    return null
  }
}

export function cerrarSesion(): void {
  localStorage.removeItem(CLAVE)
  sessionStorage.removeItem(CLAVE)
}
