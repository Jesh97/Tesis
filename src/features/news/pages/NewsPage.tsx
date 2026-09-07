import { DashboardLayout } from '../../../components/layout/DashboardLayout'
import { WebAnalyzerCard } from '../components/WebAnalyzerCard'
import { ValidationQueue } from '../components/ValidationQueue'
import { useFuentes } from '../hooks/useFuentes'

export function NewsPage() {
  const { fuentes, analizar } = useFuentes()
  const fuentesEnProceso = fuentes.filter((f) => f.estado === 'procesando' || f.estado === 'fallida')

  return (
    <DashboardLayout title="Sistema de Detección de Pesca Ilegal" searchPlaceholder="Buscar...">
      <div className="h-full overflow-y-auto p-6">
        <h1 className="text-2xl font-semibold text-slate-900">Alimentación de Base de Datos</h1>
        <p className="mt-1 max-w-2xl text-sm text-slate-500">
          Ingrese URLs de fuentes abiertas (noticias, reportes públicos) para extraer automáticamente menciones de
          incidentes marítimos utilizando procesamiento de lenguaje natural.
        </p>

        <div className="mt-6 grid grid-cols-1 gap-6 lg:grid-cols-[320px_1fr]">
          <WebAnalyzerCard onAnalizar={analizar} />
          <ValidationQueue fuentesEnProceso={fuentesEnProceso} />
        </div>
      </div>
    </DashboardLayout>
  )
}
