import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { AuditLogPage } from './AuditLogPage'

function renderPagina() {
  return render(
    <MemoryRouter>
      <AuditLogPage />
    </MemoryRouter>,
  )
}

function respuestaJson(cuerpo: unknown, status = 200): Response {
  return new Response(JSON.stringify(cuerpo), { status, headers: { 'Content-Type': 'application/json' } })
}

afterEach(() => {
  vi.restoreAllMocks()
})

describe('AuditLogPage', () => {
  it('muestra los registros con la acción, el usuario y la entidad', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        respuestaJson([
          {
            id: 'a1',
            usuario_id: 'u1',
            usuario_nombre: 'Ana Torres',
            accion: 'zona_eliminada',
            entidad: 'zona',
            entidad_id: 'z1',
            detalle: { nombre: 'Bahía X' },
            creado_en: '2026-01-15T10:00:00Z',
          },
        ]),
      ),
    )

    renderPagina()

    await waitFor(() => expect(screen.getByText('Ana Torres')).toBeInTheDocument())
    expect(screen.getByText('Zona eliminada')).toBeInTheDocument()
    expect(screen.getByText(/zona · z1/)).toBeInTheDocument()
  })

  it('muestra el mensaje de error cuando la API responde con un error', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(respuestaJson({ error: 'No tienes permiso para realizar esta acción' }, 403)))

    renderPagina()

    await waitFor(() => expect(screen.getByText('No tienes permiso para realizar esta acción')).toBeInTheDocument())
  })

  it('muestra un mensaje cuando todavía no hay registros', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(respuestaJson([])))

    renderPagina()

    await waitFor(() => expect(screen.getByText('Todavía no hay acciones registradas.')).toBeInTheDocument())
  })
})
