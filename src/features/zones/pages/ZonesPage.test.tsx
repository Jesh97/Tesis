import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'
import * as sessionModule from '../../../lib/session'
import { ZonesPage } from './ZonesPage'

// Crear/eliminar zonas exige rol "administrador" en el backend
// (server/app/routes/zonas.py) desde que se agregó requiere_rol -- estos
// tests cubren que la pantalla lo respete: sin esto, un analista vería el
// formulario y el botón de eliminar, los usaría, y solo se enteraría del
// bloqueo con un 403 después de llenar todo.
function respuestaJson(cuerpo: unknown, status = 200): Response {
  return new Response(JSON.stringify(cuerpo), { status, headers: { 'Content-Type': 'application/json' } })
}

afterEach(() => {
  vi.restoreAllMocks()
})

function renderComoRol(rol: string) {
  vi.spyOn(sessionModule, 'obtenerSesion').mockReturnValue({
    token: 't',
    id: '1',
    usuario: 'u',
    nombreCompleto: 'U',
    rol,
  })
  vi.stubGlobal(
    'fetch',
    vi.fn().mockResolvedValue(
      respuestaJson([{ id: 'z1', nombre: 'Bahía X', region: 'Lambayeque', es_critica: true, poligono: null, creado_en: '' }]),
    ),
  )
  return render(
    <MemoryRouter>
      <ZonesPage />
    </MemoryRouter>,
  )
}

describe('ZonesPage según el rol', () => {
  it('un analista no ve el formulario de nueva zona ni el botón de eliminar', async () => {
    renderComoRol('analista')

    await waitFor(() => expect(screen.getByText('Bahía X')).toBeInTheDocument())

    expect(screen.queryByRole('button', { name: 'Crear zona' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Eliminar zona' })).not.toBeInTheDocument()
    expect(screen.getByText(/reservado a un administrador/)).toBeInTheDocument()
  })

  it('un administrador sí ve el formulario y el botón de eliminar', async () => {
    renderComoRol('administrador')

    await waitFor(() => expect(screen.getByText('Bahía X')).toBeInTheDocument())

    expect(screen.getByRole('button', { name: 'Crear zona' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Eliminar zona' })).toBeInTheDocument()
  })
})
