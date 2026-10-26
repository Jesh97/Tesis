import { useEffect, useMemo, useState } from 'react'
import { DashboardLayout } from '../../../components/layout/DashboardLayout'
import { apiFetch } from '../../../lib/api'
import { MapView } from '../../monitoring/components/MapView'
import { useMmsiConIncidente } from '../../monitoring/hooks/useMmsiConIncidente'
import { useZonas } from '../../zones/hooks/useZonas'
import { Timeline, type ResumenTimeline } from '../components/Timeline'
import { useActividadMensual } from '../hooks/useActividadMensual'
import { useHistoricoMes } from '../hooks/useHistoricoMes'
import { ultimosMeses } from '../meses'
import { COLOR_VEDA, NOMBRE_RECURSO, vedasDelMes } from '../vedas'

function fechaCorta(fecha: string): string {
  const [anio, mes, dia] = fecha.split('-').map(Number)
  return new Date(anio, mes - 1, dia).toLocaleDateString('es-PE', { day: 'numeric', month: 'short', year: 'numeric' })
}

// `hasta` es el día en que la veda deja de regir: el último día de veda es el anterior.
function ultimoDia(hasta: string): string {
  const [anio, mes, dia] = hasta.split('-').map(Number)
  const fecha = new Date(anio, mes - 1, dia - 1)
  return fechaCorta(`${fecha.getFullYear()}-${fecha.getMonth() + 1}-${fecha.getDate()}`)
}

// Mismo tope que MAX_MESES en server/app/routes/actividad.py: la línea de
// tiempo usa /api/actividad/mensual para el alto de cada barra.
const MESES_TIMELINE = 36
// Tiempo que se queda en cada mes al reproducir (una vez cargado).
const MS_POR_MES = 1800

// Arranca sobre la jurisdicción de Lambayeque (de la costa hasta el borde
// oeste del bbox de GFW, ~200mn), no sobre todo el litoral como Monitoreo:
// todos los barcos del histórico salen de ese bbox.
const VISTA_LAMBAYEQUE = { centro: [-6.6, -81.4] as [number, number], zoom: 8 }

function mesesEntre(desde: string, hasta: string): string[] {
  const meses: string[] = []
  let [anio, mes] = desde.split('-').map(Number)
  const [anioFin, mesFin] = hasta.split('-').map(Number)
  while (anio < anioFin || (anio === anioFin && mes <= mesFin)) {
    meses.push(`${anio}-${String(mes).padStart(2, '0')}`)
    mes += 1
    if (mes > 12) {
      mes = 1
      anio += 1
    }
  }
  return meses
}

const [DESDE, HASTA] = ultimosMeses(MESES_TIMELINE)
const MESES = mesesEntre(DESDE, HASTA)

export function HistoricoPage() {
  const [mes, setMes] = useState(HASTA)
  const [reproduciendo, setReproduciendo] = useState(false)

  const { barcos, mesCargado, loading, error } = useHistoricoMes(mes)
  const { meses: resumenMensual } = useActividadMensual(DESDE, HASTA)
  const mmsiConIncidente = useMmsiConIncidente()
  const { zonas: todasLasZonas } = useZonas()
  const zonasCriticas = useMemo(
    () => todasLasZonas.filter((z) => z.es_critica && z.poligono).map((z) => ({ id: z.id, nombre: z.nombre, poligono: z.poligono! })),
    [todasLasZonas],
  )

  // La línea de tiempo se dibuja apenas abre la página (con barras en 0)
  // aunque /api/actividad/mensual todavía no haya respondido.
  const vedas = useMemo(() => vedasDelMes(mes), [mes])
  // En el mapa solo se dibujan las zonas específicas (paralelos/millas que
  // fija la norma): las vedas de toda la jurisdicción quedan en el panel y la
  // línea de tiempo, sin pintar todo el mar de Lambayeque.
  const zonasVeda = useMemo(
    () =>
      vedas
        .filter((v) => v.millas !== undefined || v.latitudes !== undefined)
        .map((v) => ({
        etiqueta: `Veda ${NOMBRE_RECURSO[v.recurso]}: ${v.motivo}`,
        color: COLOR_VEDA[v.recurso],
        millas: v.millas,
        latitudes: v.latitudes,
      })),
    [vedas],
  )

  const timeline: ResumenTimeline[] = useMemo(() => {
    const porMes = new Map(resumenMensual.map((m) => [m.mes, m]))
    return MESES.map((m) => ({ mes: m, buques: porMes.get(m)?.buquesPresentes ?? 0, pescando: porMes.get(m)?.buquesPescando ?? 0 }))
  }, [resumenMensual])

  // Reproducción: avanza recién cuando el mes actual ya terminó de cargar
  // (si GFW tarda en un mes fuera de cache, se espera en vez de saltearlo).
  // Mientras se muestra un mes, se pide el siguiente de fondo para que el
  // backend ya lo tenga en cache cuando toque.
  const listo = !loading && mesCargado === mes
  useEffect(() => {
    if (!reproduciendo || !listo) return
    const indice = MESES.indexOf(mes)
    if (indice >= MESES.length - 1) return
    if (indice + 2 < MESES.length) void apiFetch(`/api/actividad/historico?mes=${MESES[indice + 2]}`).catch(() => {})
    const timer = setTimeout(() => {
      setMes(MESES[indice + 1])
      // Llegó al último mes: se queda ahí y se detiene.
      if (indice + 1 === MESES.length - 1) setReproduciendo(false)
    }, MS_POR_MES)
    return () => clearTimeout(timer)
  }, [reproduciendo, listo, mes])

  function alternarReproduccion() {
    // Si está parado en el último mes, "play" vuelve a empezar desde el primero.
    if (!reproduciendo && mes === MESES[MESES.length - 1]) setMes(MESES[0])
    setReproduciendo((r) => !r)
  }

  return (
    <DashboardLayout title="Sistema de Detección de Pesca Ilegal">
      <MapView
        vessels={barcos}
        mmsiConIncidente={mmsiConIncidente}
        zonasCriticas={zonasCriticas}
        distinguirPesca
        vistaInicial={VISTA_LAMBAYEQUE}
        zonasVeda={zonasVeda}
      >
        <div className="absolute top-4 right-4 z-[1000] rounded-xl border border-slate-200 bg-white px-3 py-2 shadow-sm">
          <p className="text-sm font-semibold text-slate-900">Histórico mes a mes</p>
          <p className="text-xs text-slate-500">Posición principal de cada buque en el mes · Global Fishing Watch</p>
        </div>

        <div className="absolute top-20 right-4 z-[1000] w-80 rounded-xl border border-slate-200 bg-white px-3 py-2 shadow-sm">
          <p className="text-sm font-semibold text-slate-900">Vedas vigentes este mes</p>
          {vedas.length === 0 ? (
            <p className="text-xs text-slate-500">Sin vedas de anchoveta ni perico en Lambayeque.</p>
          ) : (
            <ul className="mt-1 space-y-1.5">
              {vedas.map((v) => (
                <li key={`${v.recurso}-${v.desde}`} className="text-xs">
                  <p className="flex items-center gap-1.5 font-medium text-slate-800">
                    <span
                      className="h-2 w-2 shrink-0 rounded-full"
                      style={{ backgroundColor: COLOR_VEDA[v.recurso] }}
                    />
                    {NOMBRE_RECURSO[v.recurso]}
                    <span className="font-normal text-slate-500">
                      · {v.mesCompleto ? 'todo el mes' : `${v.dias} días`}
                      {v.millas || v.latitudes ? ' · zona específica' : ' · toda la jurisdicción'}
                      {v.millas && `, primeras ${v.millas} mn`}
                    </span>
                  </p>
                  <p className="text-slate-600">{v.motivo}</p>
                  <p className="text-slate-400">
                    {fechaCorta(v.desde)} – {v.hasta ? ultimoDia(v.hasta) : 'vigente'} · {v.norma}
                  </p>
                </li>
              ))}
            </ul>
          )}
        </div>

        {error && (
          <div className="absolute top-4 left-1/2 z-[1000] -translate-x-1/2 rounded-lg bg-white px-3 py-1.5 text-xs text-red-600 shadow-sm">
            No se pudo cargar este mes: {error}
          </div>
        )}

        {/* left-[17rem]: deja libre la leyenda de MapView (abajo a la izquierda). */}
        <div className="absolute right-4 bottom-4 left-[17rem] z-[1000]">
          <Timeline
            meses={timeline}
            mesActual={mes}
            onCambiarMes={setMes}
            reproduciendo={reproduciendo}
            onAlternarReproduccion={alternarReproduccion}
            cargando={!listo}
            visibles={barcos.length}
          />
        </div>
      </MapView>
    </DashboardLayout>
  )
}
