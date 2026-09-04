import { DashboardLayout } from '../../../components/layout/DashboardLayout'
import { WebAnalyzerCard } from '../components/WebAnalyzerCard'
import { ValidationQueue } from '../components/ValidationQueue'

export function NewsPage() {
  return (
    <DashboardLayout title="Sistema de Detección de Pesca Ilegal" searchPlaceholder="Buscar...">
      <div className="h-full overflow-y-auto p-6">
        <h1 className="text-2xl font-semibold text-slate-900">Alimentación de Base de Datos</h1>
        <p className="mt-1 max-w-2xl text-sm text-slate-500">
          Ingrese URLs de fuentes abiertas (noticias, reportes públicos) para extraer automáticamente menciones de
          incidentes marítimos utilizando procesamiento de lenguaje natural.
        </p>

        <div className="mt-6 grid grid-cols-1 gap-6 lg:grid-cols-[320px_1fr]">
          <WebAnalyzerCard />
          <ValidationQueue />
        </div>
      </div>
    </DashboardLayout>
  )
}
