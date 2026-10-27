import { useCallback, useEffect, useState } from 'react'
import { apiFetch } from '../../../lib/api'

// Mismo mínimo que LONGITUD_MINIMA_PASSWORD en server/app/routes/usuarios.py.
export const LONGITUD_MINIMA_PASSWORD = 8

export type RolAsignable = 'supervisor' | 'analista'

export interface Usuario {
  id: string
  usuario: string
  nombre_completo: string
  rol: 'administrador' | RolAsignable
  activo: boolean
  ultimo_acceso: string | null
  creado_en: string
}

/** GET/POST /api/usuarios (solo administrador, ver server/app/routes/usuarios.py). */
export function useUsuarios() {
  const [usuarios, setUsuarios] = useState<Usuario[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const recargar = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const response = await apiFetch('/api/usuarios')
      if (!response.ok) {
        const body = (await response.json().catch(() => null)) as { error?: string } | null
        throw new Error(body?.error ?? `Error ${response.status} al listar usuarios`)
      }
      setUsuarios((await response.json()) as Usuario[])
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error desconocido')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void recargar()
  }, [recargar])

  async function crearUsuario(datos: { usuario: string; nombreCompleto: string; password: string; rol: RolAsignable }) {
    const response = await apiFetch('/api/usuarios', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(datos),
    })
    if (!response.ok) {
      const body = (await response.json().catch(() => null)) as { error?: string } | null
      throw new Error(body?.error ?? `Error ${response.status} al crear el usuario`)
    }
    await recargar()
  }

  async function cambiarPassword(id: string, password: string) {
    const response = await apiFetch(`/api/usuarios/${id}/password`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ password }),
    })
    if (!response.ok) {
      const body = (await response.json().catch(() => null)) as { error?: string } | null
      throw new Error(body?.error ?? `Error ${response.status} al cambiar la contraseña`)
    }
  }

  async function cambiarEstado(id: string, activo: boolean) {
    const response = await apiFetch(`/api/usuarios/${id}/estado`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ activo }),
    })
    if (!response.ok) {
      const body = (await response.json().catch(() => null)) as { error?: string } | null
      throw new Error(body?.error ?? `Error ${response.status} al cambiar el estado del usuario`)
    }
    await recargar()
  }

  return { usuarios, loading, error, crearUsuario, cambiarPassword, cambiarEstado }
}
