import { AlertTriangleIcon, LoaderIcon, XIcon } from '../../../components/icons'
import type { Fuente } from '../hooks/useFuentes'

// 'fallida': error técnico real (no se pudo descargar/leer el artículo, la
// IA no respondió, etc.) -- se resalta en rojo porque puede valer la pena
// reintentarla. 'descartada': el análisis SÍ funcionó, pero determinó que la
// noticia no describe una infracción concreta -- se muestra en gris neutro
// para no dar a entender que algo se rompió (ver estado_fuente en db/schema.sql).
const ESTILOS = {
  procesando: { icono: LoaderIcon, spin: true, fondo: 'bg-slate-100 text-slate-400', badge: 'bg-slate-100 text-slate-500', titulo: 'Procesando:', detalle: 'Extrayendo contenido y analizando con IA…', etiqueta: 'En Proceso' },
  fallida: { icono: AlertTriangleIcon, spin: false, fondo: 'bg-red-100 text-red-500', badge: 'bg-red-100 text-red-600', titulo: 'Falló el análisis:', detalle: 'No se pudo extraer o analizar el contenido', etiqueta: 'Fallida' },
  descartada: { icono: XIcon, spin: false, fondo: 'bg-slate-200 text-slate-500', badge: 'bg-slate-200 text-slate-600', titulo: 'Descartada:', detalle: 'La IA determinó que no describe una infracción concreta', etiqueta: 'Descartada' },
} as const

export function ProcessingRow({ item }: { item: Fuente }) {
  const estilo = ESTILOS[item.estado as keyof typeof ESTILOS] ?? ESTILOS.procesando
  const Icono = estilo.icono
  return (
    <div className="flex items-center gap-3 rounded-xl border border-slate-200 bg-white p-4">
      <span className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-full ${estilo.fondo}`}>
        <Icono className={`h-4 w-4 ${estilo.spin ? 'animate-spin' : ''}`} />
      </span>
      <div className="min-w-0 flex-1">
        <p className="truncate text-sm font-medium text-slate-700">
          {estilo.titulo} {item.dominio}
        </p>
        <p className="text-[11px] tracking-wide text-slate-400 uppercase">{estilo.detalle}</p>
      </div>
      <span className={`shrink-0 rounded px-2 py-1 text-[10px] font-bold tracking-wide uppercase ${estilo.badge}`}>
        {estilo.etiqueta}
      </span>
    </div>
  )
}
