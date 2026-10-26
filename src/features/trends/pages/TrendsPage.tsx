import { useMemo, useState } from 'react'
import { DashboardLayout } from '../../../components/layout/DashboardLayout'
import { AlertTriangleIcon, CalendarIcon, DownloadIcon, ShipIcon, TrendingUpIcon } from '../../../components/icons'
import { SelectField } from '../../../components/ui/SelectField'
import { descargarCSV } from '../../../lib/csv'
import { useMmsiConIncidente } from '../../monitoring/hooks/useMmsiConIncidente'
import { StatCard } from '../../reports/components/StatCard'
import { FishingHeatmap } from '../components/FishingHeatmap'
import { MonthlyChart, type FilaMensual, type SerieMensual } from '../components/MonthlyChart'
import { TopVesselsTable } from '../components/TopVesselsTable'
import { useActividadMensual, type ActividadMes } from '../hooks/useActividadMensual'
import { etiquetaMesLarga, ultimosMeses } from '../meses'

// Paleta categórica validada (orden fijo, ver el skill de dataviz): la
// bandera local siempre es la serie 1, y las extranjeras toman las
// siguientes según su total en el rango elegido. "Otras" va en gris neutro.
const COLORES = ['#2a78d6', '#eb6834', '#1baf7a', '#eda100']
const COLOR_OTRAS = '#94a3b8'
const BANDERA_LOCAL = 'PER'
const BANDERAS_EXTRANJERAS_VISIBLES = 3

const NOMBRES_BANDERA: Record<string, string> = {
  PER: 'Perú',
  CHN: 'China',
  ECU: 'Ecuador',
  CHL: 'Chile',
  TWN: 'Taiwán',
  KOR: 'Corea del Sur',
  ESP: 'España',
  PAN: 'Panamá',
  VUT: 'Vanuatu',
  RUS: 'Rusia',
  JPN: 'Japón',
}

const anioActual = new Date().getFullYear()
const RANGOS: { id: string; label: string; rango: [string, string] }[] = [
  { id: 'u12', label: 'Últimos 12 meses', rango: ultimosMeses(12) },
  { id: 'u24', label: 'Últimos 24 meses', rango: ultimosMeses(24) },
  { id: 'u36', label: 'Últimos 36 meses', rango: ultimosMeses(36) },
  ...[0, 1, 2, 3].map((atras) => {
    const anio = anioActual - atras
    return { id: String(anio), label: `Año ${anio}`, rango: [`${anio}-01`, `${anio}-12`] as [string, string] }
  }),
]

const formatoHoras = (v: number) =>
  v >= 1000 ? `${(v / 1000).toLocaleString('es-PE', { maximumFractionDigits: 1 })} mil` : v.toLocaleString('es-PE', { maximumFractionDigits: 0 })

/** Banderas extranjeras de pesqueros ordenadas por total en todo el rango:
 * el color sigue a la bandera (no al ranking de cada mes), así que no cambia
 * de un mes a otro. */
function seriesBanderas(meses: ActividadMes[]): SerieMensual[] {
  const totales = new Map<string, number>()
  for (const m of meses) {
    for (const [flag, n] of Object.entries(m.porBanderaPesqueros)) {
      if (flag !== BANDERA_LOCAL && flag !== 'Desconocida') totales.set(flag, (totales.get(flag) ?? 0) + n)
    }
  }
  const top = [...totales.entries()].sort((a, b) => b[1] - a[1]).slice(0, BANDERAS_EXTRANJERAS_VISIBLES)
  return [
    { key: BANDERA_LOCAL, label: NOMBRES_BANDERA[BANDERA_LOCAL], color: COLORES[0] },
    ...top.map(([flag], i) => ({ key: flag, label: NOMBRES_BANDERA[flag] ?? flag, color: COLORES[i + 1] })),
    { key: 'otras', label: 'Otras / sin bandera', color: COLOR_OTRAS },
  ]
}

function picoPor(meses: ActividadMes[], campo: (m: ActividadMes) => number): ActividadMes | null {
  return meses.reduce<ActividadMes | null>((pico, m) => (pico === null || campo(m) > campo(pico) ? m : pico), null)
}

export function TrendsPage() {
  const [rangoId, setRangoId] = useState('u24')
  const [desde, hasta] = RANGOS.find((r) => r.id === rangoId)!.rango
  const { meses, incidentesPorMes, loading, error } = useActividadMensual(desde, hasta)
  const mmsiConIncidente = useMmsiConIncidente()
  const [mesElegido, setMesElegido] = useState<string | null>(null)

  const completos = meses.filter((m) => !m.parcial)
  const picoPesca = picoPor(completos, (m) => m.horasPesca)
  const picoExtranjeros = picoPor(completos, (m) => m.pesquerosExtranjeros)
  // Si el mes elegido no está en el rango actual (se cambió el rango), se
  // vuelve al mes pico de pesca: es el que más tiene para mostrar en el mapa.
  const mesSeleccionado = meses.find((m) => m.mes === mesElegido) ?? picoPesca ?? meses[meses.length - 1] ?? null

  const banderas = useMemo(() => seriesBanderas(meses), [meses])

  const filasFlota: FilaMensual[] = meses.map((m) => ({
    mes: m.mes,
    parcial: m.parcial,
    valores: { presentes: m.pesquerosPresentes, pescando: m.buquesPescando },
  }))
  const filasHoras: FilaMensual[] = meses.map((m) => ({ mes: m.mes, parcial: m.parcial, valores: { horas: m.horasPesca } }))
  const filasBanderas: FilaMensual[] = meses.map((m) => {
    const valores: Record<string, number> = { otras: 0 }
    for (const [flag, n] of Object.entries(m.porBanderaPesqueros)) {
      if (banderas.some((b) => b.key === flag)) valores[flag] = n
      else valores.otras += n
    }
    return { mes: m.mes, parcial: m.parcial, valores }
  })
  const filasIncidentes: FilaMensual[] = meses.map((m) => ({
    mes: m.mes,
    parcial: m.parcial,
    valores: { incidentes: incidentesPorMes?.[m.mes] ?? 0 },
  }))

  const promedioPesqueros = completos.length
    ? Math.round(completos.reduce((s, m) => s + m.pesquerosPresentes, 0) / completos.length)
    : 0
  const totalHoras = meses.reduce((s, m) => s + m.horasPesca, 0)

  function exportar() {
    descargarCSV(`actividad_mensual_lambayeque_${desde}_${hasta}.csv`, [
      [
        'Mes', 'Parcial', 'Buques presentes (todos)', 'Pesqueros presentes', 'Pesqueros extranjeros',
        'Buques con pesca aparente', 'Horas de pesca aparente', 'Incidentes registrados',
      ],
      ...meses.map((m) => [
        m.mes, m.parcial ? 'sí' : 'no', m.buquesPresentes, m.pesquerosPresentes, m.pesquerosExtranjeros,
        m.buquesPescando, m.horasPesca, incidentesPorMes?.[m.mes] ?? '',
      ]),
    ])
  }

  const graficoComun = { mesSeleccionado: mesSeleccionado?.mes ?? null, onSeleccionarMes: setMesElegido }

  return (
    <DashboardLayout title="Sistema de Detección de Pesca Ilegal" searchPlaceholder="Buscar embarcación...">
      <div className="h-full overflow-y-auto">
        <div className="p-6">
          <div className="flex flex-wrap items-end justify-between gap-4">
            <div>
              <h1 className="text-2xl font-semibold text-slate-900">Comportamiento mensual</h1>
              <p className="mt-1 max-w-2xl text-sm text-slate-500">
                Actividad AIS de embarcaciones en la jurisdicción marítima de Lambayeque, mes a mes, según Global
                Fishing Watch.
              </p>
            </div>
            <div className="flex items-end gap-3">
              <div className="w-52">
                <SelectField
                  id="rango-tendencias"
                  label="Periodo"
                  icon={<CalendarIcon className="h-4 w-4" />}
                  value={rangoId}
                  onChange={(e) => setRangoId(e.target.value)}
                >
                  {RANGOS.map((r) => (
                    <option key={r.id} value={r.id}>
                      {r.label}
                    </option>
                  ))}
                </SelectField>
              </div>
              <button
                onClick={exportar}
                disabled={loading || meses.length === 0}
                className="flex items-center gap-2 rounded-lg border border-slate-300 bg-white px-4 py-2.5 text-sm font-medium text-slate-700 shadow-sm hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50"
              >
                <DownloadIcon className="h-4 w-4" />
                Exportar CSV
              </button>
            </div>
          </div>

          {error && <p className="mt-6 text-sm text-red-600">No se pudo consultar Global Fishing Watch: {error}</p>}
          {!error && loading && (
            <p className="mt-6 text-sm text-slate-500">
              Consultando Global Fishing Watch… la primera vez por año puede tardar hasta un minuto.
            </p>
          )}

          {!error && !loading && meses.length > 0 && mesSeleccionado && (
            <>
              <div className="mt-6 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
                <StatCard
                  label="Pesqueros promedio / mes"
                  value={promedioPesqueros.toLocaleString('es-PE')}
                  icon={<ShipIcon className="h-4 w-4 text-sky-600" />}
                  iconClassName="bg-sky-100"
                />
                <StatCard
                  label="Horas de pesca aparente"
                  value={formatoHoras(totalHoras)}
                  icon={<TrendingUpIcon className="h-4 w-4 text-slate-600" />}
                  iconClassName="bg-slate-100"
                />
                <StatCard
                  label="Mes pico de pesca"
                  value={picoPesca && picoPesca.horasPesca > 0 ? etiquetaMesLarga(picoPesca.mes) : '—'}
                  icon={<CalendarIcon className="h-4 w-4 text-slate-600" />}
                  iconClassName="bg-slate-100"
                />
                <StatCard
                  label="Máx. pesqueros extranjeros"
                  value={
                    picoExtranjeros
                      ? `${picoExtranjeros.pesquerosExtranjeros} · ${etiquetaMesLarga(picoExtranjeros.mes)}`
                      : '—'
                  }
                  icon={<AlertTriangleIcon className="h-4 w-4 text-amber-600" />}
                  iconClassName="bg-amber-100"
                />
              </div>

              <div className="mt-6 grid grid-cols-1 gap-6 xl:grid-cols-2">
                <MonthlyChart
                  {...graficoComun}
                  titulo="Flota pesquera por mes"
                  subtitulo="Embarcaciones pesqueras distintas con AIS en la zona, y cuántas tuvieron pesca aparente."
                  tipo="line"
                  series={[
                    { key: 'presentes', label: 'Pesqueros presentes', color: COLORES[0] },
                    { key: 'pescando', label: 'Con pesca aparente', color: COLORES[1] },
                  ]}
                  filas={filasFlota}
                />
                <MonthlyChart
                  {...graficoComun}
                  titulo="Horas de pesca aparente por mes"
                  subtitulo="Suma de horas en que el modelo de GFW detecta patrón de pesca."
                  tipo="bar"
                  series={[{ key: 'horas', label: 'Horas', color: COLORES[0] }]}
                  filas={filasHoras}
                  formatear={formatoHoras}
                />
                <MonthlyChart
                  {...graficoComun}
                  titulo="Pesqueros por bandera"
                  subtitulo="Embarcaciones pesqueras distintas por mes, según su bandera."
                  tipo="stacked"
                  series={banderas}
                  filas={filasBanderas}
                />
                <MonthlyChart
                  {...graficoComun}
                  titulo="Incidentes registrados por mes"
                  subtitulo={
                    incidentesPorMes
                      ? 'Incidentes del sistema (todas las zonas), por fecha de detección.'
                      : 'No se pudieron cargar los incidentes desde la base de datos.'
                  }
                  tipo="bar"
                  series={[{ key: 'incidentes', label: 'Incidentes', color: COLORES[0] }]}
                  filas={filasIncidentes}
                  alto={160}
                />
              </div>

              <div className="mt-6 grid grid-cols-1 gap-6 xl:grid-cols-[1fr_400px]">
                <FishingHeatmap mes={mesSeleccionado.mes} celdas={mesSeleccionado.celdas} />
                <TopVesselsTable
                  mes={mesSeleccionado.mes}
                  buques={mesSeleccionado.topBuques}
                  mmsiConIncidente={mmsiConIncidente}
                />
              </div>

              <details className="mt-6 rounded-xl border border-slate-200 bg-white p-5">
                <summary className="cursor-pointer text-sm font-semibold text-slate-900">Ver tabla de datos</summary>
                <div className="mt-4 overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b border-slate-100 text-left text-[11px] font-semibold tracking-wide text-slate-400 uppercase">
                        <th className="pb-2">Mes</th>
                        <th className="pb-2 text-right">Buques (todos)</th>
                        <th className="pb-2 text-right">Pesqueros</th>
                        <th className="pb-2 text-right">Pesqueros extranjeros</th>
                        <th className="pb-2 text-right">Con pesca aparente</th>
                        <th className="pb-2 text-right">Horas de pesca</th>
                        <th className="pb-2 text-right">Incidentes</th>
                      </tr>
                    </thead>
                    <tbody className="tabular-nums">
                      {meses.map((m) => (
                        <tr key={m.mes} className="border-b border-slate-50 last:border-0">
                          <td className="py-1.5 text-slate-700 capitalize">
                            {etiquetaMesLarga(m.mes)}
                            {m.parcial && <span className="ml-1 text-xs text-slate-400 normal-case">(parcial)</span>}
                          </td>
                          <td className="py-1.5 text-right text-slate-600">{m.buquesPresentes}</td>
                          <td className="py-1.5 text-right text-slate-600">{m.pesquerosPresentes}</td>
                          <td className="py-1.5 text-right text-slate-600">{m.pesquerosExtranjeros}</td>
                          <td className="py-1.5 text-right text-slate-600">{m.buquesPescando}</td>
                          <td className="py-1.5 text-right text-slate-600">
                            {m.horasPesca.toLocaleString('es-PE', { maximumFractionDigits: 1 })}
                          </td>
                          <td className="py-1.5 text-right text-slate-600">{incidentesPorMes?.[m.mes] ?? '—'}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </details>

              <p className="mt-4 text-xs leading-relaxed text-slate-400">
                Fuente: Global Fishing Watch (datasets públicos de presencia AIS y esfuerzo pesquero). Solo incluye
                embarcaciones que transmiten AIS: buena parte de la flota artesanal no lo hace. La "pesca aparente" la
                infiere un modelo a partir del movimiento, no es una medición directa. Los datos se publican con
                algunos días de rezago, así que el mes en curso (marcado como parcial) y los meses muy recientes
                pueden estar incompletos.
              </p>
            </>
          )}
        </div>
      </div>
    </DashboardLayout>
  )
}
