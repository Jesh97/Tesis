import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { apiFetch } from './api'
import { guardarSesion } from './session'

const SESION = { token: 'token-de-prueba', id: '1', usuario: 'ana', nombreCompleto: 'Ana', rol: 'analista' }

function respuesta(status: number): Response {
  return new Response(null, { status })
}

beforeEach(() => {
  localStorage.clear()
  sessionStorage.clear()
})

afterEach(() => {
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

describe('apiFetch', () => {
  it('adjunta el header Authorization cuando hay sesión guardada', async () => {
    guardarSesion(SESION, true)
    const fetchMock = vi.fn().mockResolvedValue(respuesta(200))
    vi.stubGlobal('fetch', fetchMock)

    await apiFetch('/api/incidentes')

    const [, opciones] = fetchMock.mock.calls[0]
    const headers = new Headers(opciones.headers)
    expect(headers.get('Authorization')).toBe('Bearer token-de-prueba')
  })

  it('no manda Authorization cuando no hay sesión', async () => {
    const fetchMock = vi.fn().mockResolvedValue(respuesta(200))
    vi.stubGlobal('fetch', fetchMock)

    await apiFetch('/api/auth/login', { method: 'POST' })

    const [, opciones] = fetchMock.mock.calls[0]
    const headers = new Headers(opciones.headers)
    expect(headers.has('Authorization')).toBe(false)
  })

  it('en un 401 cierra la sesión guardada', async () => {
    guardarSesion(SESION, true)
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(respuesta(401)))

    await apiFetch('/api/incidentes')

    expect(localStorage.getItem('pesca_ilegal_sesion')).toBeNull()
    expect(sessionStorage.getItem('pesca_ilegal_sesion')).toBeNull()
  })

  it('en una respuesta ok no toca la sesión', async () => {
    guardarSesion(SESION, true)
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(respuesta(200)))

    await apiFetch('/api/incidentes')

    expect(localStorage.getItem('pesca_ilegal_sesion')).not.toBeNull()
  })

  it('devuelve la respuesta tal cual para que el caller decida qué hacer', async () => {
    const esperada = respuesta(404)
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(esperada))

    const recibida = await apiFetch('/api/incidentes/no-existe')

    expect(recibida).toBe(esperada)
  })
})
