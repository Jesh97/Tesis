import { render, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { ErrorBoundary } from './ErrorBoundary'

function ComponenteQueRevienta(): never {
  throw new Error('fallo simulado de render')
}

beforeEach(() => {
  // React (y jsdom) logean el error de render a consola además de pasar por
  // componentDidCatch -- se silencia acá para no ensuciar la salida del test,
  // no porque el error en sí sea inesperado (es justo lo que se está probando).
  vi.spyOn(console, 'error').mockImplementation(() => {})
})

afterEach(() => {
  vi.restoreAllMocks()
})

describe('ErrorBoundary', () => {
  it('muestra el contenido normal cuando el hijo no falla', () => {
    render(
      <ErrorBoundary>
        <p>Contenido normal</p>
      </ErrorBoundary>,
    )
    expect(screen.getByText('Contenido normal')).toBeInTheDocument()
  })

  it('atrapa un error de render y muestra el mensaje de recuperación en vez de tumbar la página', () => {
    render(
      <ErrorBoundary>
        <ComponenteQueRevienta />
      </ErrorBoundary>,
    )

    expect(screen.getByText('Ocurrió un error al mostrar esta página.')).toBeInTheDocument()
    expect(screen.getByText(/fallo simulado de render/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Recargar página' })).toBeInTheDocument()
  })
})
