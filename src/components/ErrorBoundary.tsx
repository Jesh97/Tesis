import { Component, type ErrorInfo, type ReactNode } from 'react'

interface Props {
  children: ReactNode
}

interface State {
  error: Error | null
}

/** Sin esto, un error de render en CUALQUIER página (un campo que cambió de
 * nombre en el backend, un undefined inesperado, etc.) tumbaba TODA la app
 * a una pantalla en blanco, sin ningún mensaje -- justo lo que pasó con el
 * Dashboard de Reportes cuando el backend todavía no tenía las columnas
 * nuevas. React no recupera solo de un error de render: hace falta este
 * boundary (debe ser un componente de clase, la única forma de implementar
 * componentDidCatch/getDerivedStateFromError). */
export class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null }

  static getDerivedStateFromError(error: Error): State {
    return { error }
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error('Error de render sin capturar:', error, info.componentStack)
  }

  render() {
    if (this.state.error) {
      return (
        <div className="flex min-h-svh flex-col items-center justify-center gap-3 bg-slate-50 p-6 text-center">
          <p className="text-sm font-semibold text-slate-900">Ocurrió un error al mostrar esta página.</p>
          <p className="max-w-md text-xs text-slate-500">
            {this.state.error.message || 'Error desconocido.'} Si esto sigue pasando después de recargar,
            contacta a soporte técnico.
          </p>
          <button
            onClick={() => window.location.reload()}
            className="mt-2 rounded-lg bg-slate-900 px-4 py-2 text-xs font-semibold text-white hover:bg-slate-800"
          >
            Recargar página
          </button>
        </div>
      )
    }
    return this.props.children
  }
}
