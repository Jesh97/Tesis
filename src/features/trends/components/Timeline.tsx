import { ChevronLeftIcon, ChevronRightIcon, LoaderIcon, PlayIcon } from '../../../components/icons'
import { etiquetaMes, etiquetaMesLarga } from '../meses'
import { COLOR_VEDA, diasDeVeda, type RecursoVeda } from '../vedas'

// Franja bajo las barras: una fila por recurso, más intensa cuantos más
// días del mes estuvo en veda.
const FILAS_VEDA: { recurso: RecursoVeda; etiqueta: string; color: string }[] = [
  { recurso: 'anchoveta', etiqueta: 'Veda anchoveta', color: COLOR_VEDA.anchoveta },
  { recurso: 'perico', etiqueta: 'Veda perico', color: COLOR_VEDA.perico },
]

function diasDelMes(mes: string): number {
  const [anio, m] = mes.split('-').map(Number)
  return new Date(anio, m, 0).getDate()
}

export interface ResumenTimeline {
  mes: string
  buques: number
  pescando: number
}

interface TimelineProps {
  meses: ResumenTimeline[]
  mesActual: string
  onCambiarMes: (mes: string) => void
  reproduciendo: boolean
  onAlternarReproduccion: () => void
  cargando: boolean
  /** Cuántos barcos se ven en el mapa ahora. */
  visibles: number
}

const ALTO_BARRAS = 44

/** Línea de tiempo del Histórico: una barra por mes (alto = buques con AIS,
 * y en azul la parte que tuvo pesca aparente -- es un subconjunto, por eso
 * va anidada y no apilada). Click en una barra salta a ese mes. */
export function Timeline({
  meses,
  mesActual,
  onCambiarMes,
  reproduciendo,
  onAlternarReproduccion,
  cargando,
  visibles,
}: TimelineProps) {
  const indice = meses.findIndex((m) => m.mes === mesActual)
  const maximo = Math.max(1, ...meses.map((m) => m.buques))
  const resumen = meses[indice]

  return (
    <div className="rounded-xl border border-slate-200 bg-white/95 p-3 shadow-lg backdrop-blur">
      <div className="flex flex-wrap items-center gap-3">
        <div className="flex items-center gap-1">
          <button
            type="button"
            aria-label="Mes anterior"
            disabled={indice <= 0}
            onClick={() => onCambiarMes(meses[indice - 1].mes)}
            className="flex h-8 w-8 items-center justify-center rounded-lg text-slate-600 hover:bg-slate-100 disabled:opacity-30"
          >
            <ChevronLeftIcon className="h-4 w-4" />
          </button>
          <button
            type="button"
            aria-label={reproduciendo ? 'Pausar' : 'Reproducir mes a mes'}
            onClick={onAlternarReproduccion}
            className="flex h-8 w-8 items-center justify-center rounded-lg bg-slate-900 text-white hover:bg-slate-700"
          >
            {reproduciendo ? (
              <span className="flex gap-0.5">
                <span className="h-3 w-1 rounded-sm bg-white" />
                <span className="h-3 w-1 rounded-sm bg-white" />
              </span>
            ) : (
              <PlayIcon className="h-4 w-4" />
            )}
          </button>
          <button
            type="button"
            aria-label="Mes siguiente"
            disabled={indice >= meses.length - 1}
            onClick={() => onCambiarMes(meses[indice + 1].mes)}
            className="flex h-8 w-8 items-center justify-center rounded-lg text-slate-600 hover:bg-slate-100 disabled:opacity-30"
          >
            <ChevronRightIcon className="h-4 w-4" />
          </button>
        </div>

        <div className="min-w-40">
          <p className="flex items-center gap-1.5 text-sm font-semibold text-slate-900 capitalize">
            {etiquetaMesLarga(mesActual)}
            {cargando && <LoaderIcon className="h-3.5 w-3.5 animate-spin text-slate-400" />}
          </p>
          <p className="text-xs text-slate-500">
            {visibles.toLocaleString('es-PE')} en el mapa
            {resumen && ` · ${resumen.pescando.toLocaleString('es-PE')} con pesca aparente`}
          </p>
        </div>

        <div className="ml-auto flex items-center gap-3 text-[11px] text-slate-500">
          <span className="flex items-center gap-1.5">
            <span className="h-2.5 w-2.5 rounded-sm bg-slate-300" /> Buques con AIS
          </span>
          <span className="flex items-center gap-1.5">
            <span className="h-2.5 w-2.5 rounded-sm bg-[#2a78d6]" /> Con pesca aparente
          </span>
          {FILAS_VEDA.map((fila) => (
            <span key={fila.recurso} className="flex items-center gap-1.5">
              <span className="h-1.5 w-2.5 rounded-sm" style={{ backgroundColor: fila.color }} /> {fila.etiqueta}
            </span>
          ))}
        </div>
      </div>

      <div className="mt-2 flex items-end gap-0.5" style={{ height: ALTO_BARRAS }}>
        {meses.map((m) => {
          const actual = m.mes === mesActual
          return (
            <button
              key={m.mes}
              type="button"
              onClick={() => onCambiarMes(m.mes)}
              title={`${etiquetaMesLarga(m.mes)}: ${m.buques} buques, ${m.pescando} con pesca aparente`}
              aria-label={etiquetaMesLarga(m.mes)}
              className={`group relative flex h-full flex-1 items-end justify-center rounded-sm ${actual ? 'bg-slate-100' : 'hover:bg-slate-50'}`}
            >
              <span
                className={`absolute bottom-0 w-[70%] rounded-t-sm ${actual ? 'bg-slate-500' : 'bg-slate-300 group-hover:bg-slate-400'}`}
                style={{ height: `${(m.buques / maximo) * 100}%` }}
              />
              <span
                className="absolute bottom-0 w-[70%] rounded-t-sm bg-[#2a78d6]"
                style={{ height: m.pescando > 0 ? `${Math.max((m.pescando / maximo) * 100, 3)}%` : 0 }}
              />
            </button>
          )
        })}
      </div>
      {FILAS_VEDA.map((fila) => (
        <div key={fila.recurso} className="mt-0.5 flex gap-0.5">
          {meses.map((m) => {
            const dias = diasDeVeda(m.mes, fila.recurso)
            return (
              <span
                key={m.mes}
                title={dias > 0 ? `${fila.etiqueta}: ${dias} días en ${etiquetaMesLarga(m.mes)}` : undefined}
                className="h-1.5 flex-1 rounded-sm"
                style={{ backgroundColor: fila.color, opacity: dias > 0 ? 0.3 + 0.7 * Math.min(dias / diasDelMes(m.mes), 1) : 0 }}
              />
            )
          })}
        </div>
      ))}
      <div className="mt-1 flex gap-0.5">
        {meses.map((m, i) => (
          <span
            key={m.mes}
            className={`flex-1 text-center text-[10px] ${m.mes === mesActual ? 'font-semibold text-slate-900' : 'text-slate-400'}`}
          >
            {m.mes.endsWith('-01') || i === 0 ? etiquetaMes(m.mes, true) : m.mes.endsWith('-07') ? etiquetaMes(m.mes) : ''}
          </span>
        ))}
      </div>
    </div>
  )
}
