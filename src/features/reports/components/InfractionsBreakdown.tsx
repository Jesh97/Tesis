import type { TipoInfraccionResumen } from '../hooks/useReportes'

// Mismo color que el punto de la leyenda (clases de abajo), en hex para el
// trazo del SVG -- Tailwind no deja usar sus clases dentro de un atributo
// stroke calculado dinámicamente.
const colorHex: Record<TipoInfraccionResumen['color_indicador'], string> = {
  red: '#ef4444',
  amber: '#fbbf24',
  gray: '#cbd5e1',
  dark: '#0f172a',
}

const colorClasses: Record<TipoInfraccionResumen['color_indicador'], string> = {
  red: 'bg-red-500',
  amber: 'bg-amber-400',
  gray: 'bg-slate-300',
  dark: 'bg-slate-900',
}

const RADIO = 52
const GROSOR = 16
const CIRCUNFERENCIA = 2 * Math.PI * RADIO
// Separación visual entre segmentos (mark spec: gap de superficie entre
// arcos contiguos, para no verlos pegados como si fueran uno solo).
const GAP_PX = 3

function Donut({ data, total }: { data: TipoInfraccionResumen[]; total: number }) {
  let acumulado = 0
  const segmentos = data.map((tipo) => {
    const largo = Math.max((tipo.total / total) * CIRCUNFERENCIA - GAP_PX, 0)
    const offset = -acumulado
    acumulado += (tipo.total / total) * CIRCUNFERENCIA
    return { ...tipo, largo, offset }
  })

  return (
    <svg viewBox="0 0 128 128" className="h-32 w-32 -rotate-90">
      <circle cx="64" cy="64" r={RADIO} fill="none" stroke="#f1f5f9" strokeWidth={GROSOR} />
      {segmentos.map((s) => (
        <circle
          key={s.nombre}
          cx="64"
          cy="64"
          r={RADIO}
          fill="none"
          stroke={colorHex[s.color_indicador]}
          strokeWidth={GROSOR}
          strokeDasharray={`${s.largo} ${CIRCUNFERENCIA - s.largo}`}
          strokeDashoffset={s.offset}
          strokeLinecap="round"
        />
      ))}
    </svg>
  )
}

export function InfractionsBreakdown({ data }: { data: TipoInfraccionResumen[] }) {
  const total = data.reduce((suma, d) => suma + d.total, 0)
  // Los tipos en 0 no aportan nada al donut ni a la lista -- antes se
  // mostraban igual ("Contaminación 0%", "Velocidad Inusual 0%"...), puro
  // ruido visual sin información real.
  const conDatos = data.filter((d) => d.total > 0)

  return (
    <div className="rounded-xl border border-slate-200 bg-white p-5">
      <h2 className="text-sm font-semibold text-slate-900">Tipos de Infracciones</h2>

      {total === 0 ? (
        <p className="mt-10 text-center text-sm text-slate-400">Todavía no hay incidentes registrados.</p>
      ) : (
        <>
          <div className="relative mt-4 flex justify-center">
            <Donut data={conDatos} total={total} />
            <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center">
              <span className="text-lg font-bold text-slate-900">{total.toLocaleString('es-PE')}</span>
              <span className="text-[10px] tracking-wide text-slate-400 uppercase">incidentes</span>
            </div>
          </div>

          <ul className="mt-5 flex flex-col gap-2.5">
            {conDatos.map((tipo) => (
              <li key={tipo.nombre} className="flex items-center justify-between text-sm">
                <span className="flex items-center gap-2 text-slate-600">
                  <span className={`h-2.5 w-2.5 shrink-0 rounded-full ${colorClasses[tipo.color_indicador]}`} />
                  {tipo.nombre}
                </span>
                <span className="font-semibold text-slate-800">{tipo.porcentaje ?? 0}%</span>
              </li>
            ))}
          </ul>
        </>
      )}
    </div>
  )
}
