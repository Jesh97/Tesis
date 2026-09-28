import { beforeEach, describe, expect, it } from 'vitest'
import { cerrarSesion, guardarSesion, obtenerSesion, type Sesion } from './session'

const SESION_DE_PRUEBA: Sesion = {
  token: 'abc.def.ghi',
  id: '1',
  usuario: 'ana',
  nombreCompleto: 'Ana Torres',
  rol: 'analista',
}

beforeEach(() => {
  localStorage.clear()
  sessionStorage.clear()
})

describe('guardarSesion / obtenerSesion', () => {
  it('con recordar=true guarda en localStorage y limpia sessionStorage', () => {
    sessionStorage.setItem('pesca_ilegal_sesion', 'basura-previa')
    guardarSesion(SESION_DE_PRUEBA, true)

    expect(JSON.parse(localStorage.getItem('pesca_ilegal_sesion')!)).toEqual(SESION_DE_PRUEBA)
    expect(sessionStorage.getItem('pesca_ilegal_sesion')).toBeNull()
  })

  it('con recordar=false guarda en sessionStorage y limpia localStorage', () => {
    localStorage.setItem('pesca_ilegal_sesion', 'basura-previa')
    guardarSesion(SESION_DE_PRUEBA, false)

    expect(JSON.parse(sessionStorage.getItem('pesca_ilegal_sesion')!)).toEqual(SESION_DE_PRUEBA)
    expect(localStorage.getItem('pesca_ilegal_sesion')).toBeNull()
  })

  it('nunca deja la sesión en ambos storages a la vez', () => {
    guardarSesion(SESION_DE_PRUEBA, true)
    guardarSesion(SESION_DE_PRUEBA, false)

    expect(localStorage.getItem('pesca_ilegal_sesion')).toBeNull()
    expect(sessionStorage.getItem('pesca_ilegal_sesion')).not.toBeNull()
  })

  it('obtenerSesion prioriza localStorage sobre sessionStorage', () => {
    localStorage.setItem('pesca_ilegal_sesion', JSON.stringify({ ...SESION_DE_PRUEBA, usuario: 'de-localStorage' }))
    sessionStorage.setItem('pesca_ilegal_sesion', JSON.stringify({ ...SESION_DE_PRUEBA, usuario: 'de-sessionStorage' }))

    expect(obtenerSesion()?.usuario).toBe('de-localStorage')
  })

  it('devuelve null si no hay ninguna sesión guardada', () => {
    expect(obtenerSesion()).toBeNull()
  })

  it('devuelve null (no lanza) si el contenido guardado no es JSON válido', () => {
    localStorage.setItem('pesca_ilegal_sesion', 'esto no es json{{{')
    expect(obtenerSesion()).toBeNull()
  })
})

describe('cerrarSesion', () => {
  it('borra la sesión de ambos storages', () => {
    localStorage.setItem('pesca_ilegal_sesion', JSON.stringify(SESION_DE_PRUEBA))
    sessionStorage.setItem('pesca_ilegal_sesion', JSON.stringify(SESION_DE_PRUEBA))

    cerrarSesion()

    expect(localStorage.getItem('pesca_ilegal_sesion')).toBeNull()
    expect(sessionStorage.getItem('pesca_ilegal_sesion')).toBeNull()
  })
})
