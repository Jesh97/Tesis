import { useEffect, useRef, useState } from 'react'
import { etiquetaMes, etiquetaMesLarga } from '../meses'

export interface SerieMensual {
  key: string
  label: string
  color: string
}

export interface FilaMensual {
  mes: string
  parcial?: boolean
  valores: Record<string, number>
}

interface MonthlyChartProps {
  titulo: string
  subtitulo?: string
  tipo: 'line' | 'bar' | 'stacked'
  series: SerieMensual[]
  filas: FilaMensual[]
  mesSeleccionado: string | null
  onSeleccionarMes: (mes: string) => void
  formatear?: (valor: number) => string
  alto?: number
}

const MARGEN = { top: 12, right: 12, bottom: 24, left: 44 }
const formatoPorDefecto = (v: number) => v.toLocaleString('es-PE', { maximumFractionDigits: 0 })

/** Ancho real del contenedor: el SVG se dibuja en píxeles (no con viewBox
 * estirado) para que los textos y el grosor de las líneas no se deformen. */
function useAncho<T extends HTMLElement>() {
  const ref = useRef<T>(null)
  const [ancho, setAncho] = useState(0)
  useEffect(() => {
    if (!ref.current) return
    const observer = new ResizeObserver(([entrada]) => setAncho(entrada.contentRect.width))
    observer.observe(ref.current)
    return () => observer.disconnect()
  }, [])
  return [ref, ancho] as const
}

/** Escala "linda" para el eje Y: 4 divisiones con pasos de 1/2/5 x 10^n. */
function ticksEjeY(maximo: number): number[] {
  if (maximo <= 0) return [0, 1]
  const pasoCrudo = maximo / 4
  const magnitud = 10 ** Math.floor(Math.log10(pasoCrudo))
  const paso = [1, 2, 5, 10].map((m) => m * magnitud).find((p) => p >= pasoCrudo) ?? pasoCrudo
  const ticks = []
  for (let v = 0; v < maximo + paso; v += paso) ticks.push(v)
  return ticks
}

/** Gráfico mes a mes compartido por toda la vista "Tendencias". Cada columna
 * (un mes) es un área de click/hover completa -- no solo la barra o el punto,
 * que pueden ser diminutos -- y al hacer click selecciona ese mes para el
 * mapa de calor y la tabla de buques. */
export function MonthlyChart({
  titulo,
  subtitulo,
  tipo,
  series,
  filas,
  mesSeleccionado,
  onSeleccionarMes,
  formatear = formatoPorDefecto,
  alto = 200,
}: MonthlyChartProps) {
  const [contenedorRef, ancho] = useAncho<HTMLDivElement>()
  const [hover, setHover] = useState<number | null>(null)

  const totalFila = (f: FilaMensual) =>
    tipo === 'stacked'
      ? series.reduce((suma, s) => suma + (f.valores[s.key] ?? 0), 0)
      : Math.max(...series.map((s) => f.valores[s.key] ?? 0))
  const ticks = ticksEjeY(Math.max(0, ...filas.map(totalFila)))
  const maxY = ticks[ticks.length - 1]

  const anchoPlot = Math.max(0, ancho - MARGEN.left - MARGEN.right)
  const altoPlot = alto - MARGEN.top - MARGEN.bottom
  const banda = filas.length > 0 ? anchoPlot / filas.length : 0
  const y = (v: number) => MARGEN.top + altoPlot - (v / maxY) * altoPlot
  const xCentro = (i: number) => MARGEN.left + banda * i + banda / 2
  // Barra fina con aire entre columnas (gap de superficie, no un borde).
  const anchoBarra = Math.max(2, Math.min(28, banda - 4))
  // Con muchos meses no entran todas las etiquetas: se muestra 1 de cada 3,
  // siempre incluyendo enero (donde cambia el año).
  const cadaCuanto = filas.length > 14 ? 3 : 1

  const filaHover = hover !== null ? filas[hover] : null
  const leyenda = series.length >= 2

  return (
    <div className="rounded-xl border border-slate-200 bg-white p-5">
      <div className="flex flex-wrap items-start justify-between gap-x-4 gap-y-2">
        <div>
          <h2 className="text-sm font-semibold text-slate-900">{titulo}</h2>
          {subtitulo && <p className="mt-0.5 text-xs text-slate-500">{subtitulo}</p>}
        </div>
        {leyenda && (
          <ul className="flex flex-wrap items-center gap-x-3 gap-y-1">
            {series.map((s) => (
              <li key={s.key} className="flex items-center gap-1.5 text-xs text-slate-600">
                <span
                  className={tipo === 'line' ? 'h-0.5 w-3 rounded-full' : 'h-2.5 w-2.5 rounded-sm'}
                  style={{ backgroundColor: s.color }}
                />
                {s.label}
              </li>
            ))}
          </ul>
        )}
      </div>

      <div ref={contenedorRef} className="relative mt-4" style={{ height: alto }}>
        {ancho > 0 && (
          <svg width={ancho} height={alto} role="img" aria-label={titulo} onMouseLeave={() => setHover(null)}>
            {ticks.map((t) => (
              <g key={t}>
                <line x1={MARGEN.left} x2={ancho - MARGEN.right} y1={y(t)} y2={y(t)} stroke="#f1f5f9" />
                <text x={MARGEN.left - 6} y={y(t)} dy="0.32em" textAnchor="end" className="fill-slate-400 text-[10px]">
                  {formatear(t)}
                </text>
              </g>
            ))}

            {filas.map((f, i) => {
              const seleccionado = f.mes === mesSeleccionado
              return (
                <g key={f.mes}>
                  {(seleccionado || hover === i) && (
                    <rect
                      x={MARGEN.left + banda * i}
                      y={MARGEN.top}
                      width={banda}
                      height={altoPlot}
                      className={seleccionado ? 'fill-slate-100' : 'fill-slate-50'}
                    />
                  )}
                  {(i % cadaCuanto === 0 || f.mes.endsWith('-01')) && (
                    <text
                      x={xCentro(i)}
                      y={alto - 6}
                      textAnchor="middle"
                      className={`text-[10px] ${seleccionado ? 'fill-slate-900 font-semibold' : 'fill-slate-400'}`}
                    >
                      {etiquetaMes(f.mes, f.mes.endsWith('-01') || i === 0)}
                    </text>
                  )}
                </g>
              )
            })}

            {tipo !== 'line' &&
              filas.map((f, i) => {
                let acumulado = 0
                const segmentos = tipo === 'stacked' ? series : series.slice(0, 1)
                return segmentos.map((s) => {
                  const valor = f.valores[s.key] ?? 0
                  if (valor <= 0) return null
                  const base = acumulado
                  acumulado += valor
                  const yArriba = y(acumulado)
                  // 2px de superficie entre segmentos apilados.
                  const altoSeg = Math.max(1, y(base) - yArriba - (tipo === 'stacked' && base > 0 ? 2 : 0))
                  return (
                    <rect
                      key={s.key}
                      x={xCentro(i) - anchoBarra / 2}
                      y={yArriba}
                      width={anchoBarra}
                      height={altoSeg}
                      rx={acumulado === totalFila(f) ? 2 : 0}
                      fill={s.color}
                      opacity={f.parcial ? 0.45 : 1}
                    />
                  )
                })
              })}

            {tipo === 'line' &&
              series.map((s) => (
                <g key={s.key}>
                  <polyline
                    fill="none"
                    stroke={s.color}
                    strokeWidth={2}
                    strokeLinejoin="round"
                    points={filas.map((f, i) => `${xCentro(i)},${y(f.valores[s.key] ?? 0)}`).join(' ')}
                  />
                  {hover !== null && (
                    <circle
                      cx={xCentro(hover)}
                      cy={y(filas[hover].valores[s.key] ?? 0)}
                      r={4}
                      fill={s.color}
                      stroke="white"
                      strokeWidth={2}
                    />
                  )}
                </g>
              ))}

            {/* Áreas de hover/click: la columna completa de cada mes. */}
            {filas.map((f, i) => (
              <rect
                key={f.mes}
                x={MARGEN.left + banda * i}
                y={MARGEN.top}
                width={banda}
                height={altoPlot}
                fill="transparent"
                className="cursor-pointer"
                onMouseEnter={() => setHover(i)}
                onClick={() => onSeleccionarMes(f.mes)}
              >
                <title>{etiquetaMesLarga(f.mes)}</title>
              </rect>
            ))}
          </svg>
        )}

        {filaHover && hover !== null && (
          <div
            className="pointer-events-none absolute top-0 z-10 min-w-36 rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs shadow-md"
            style={
              xCentro(hover) > ancho / 2
                ? { right: ancho - xCentro(hover) + 8 }
                : { left: xCentro(hover) + 8 }
            }
          >
            <p className="font-semibold text-slate-900 capitalize">
              {etiquetaMesLarga(filaHover.mes)}
              {filaHover.parcial && <span className="ml-1 font-normal text-slate-400">(parcial)</span>}
            </p>
            <ul className="mt-1 space-y-0.5">
              {series.map((s) => (
                <li key={s.key} className="flex items-center justify-between gap-3 text-slate-600">
                  <span className="flex items-center gap-1.5">
                    {series.length > 1 && <span className="h-2 w-2 rounded-sm" style={{ backgroundColor: s.color }} />}
                    {s.label}
                  </span>
                  <span className="font-medium text-slate-900 tabular-nums">{formatear(filaHover.valores[s.key] ?? 0)}</span>
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </div>
  )
}
