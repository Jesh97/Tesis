import { useMemo, useState, type ReactNode } from 'react'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import { CircleMarker, MapContainer, Marker, Polygon, Popup, TileLayer, Tooltip, useMap } from 'react-leaflet'
import * as turf from '@turf/turf'
import { MinusIcon, PlusIcon } from '../../../components/icons'
import { apiFetch } from '../../../lib/api'
import { LAMBAYEQUE_COASTLINE } from '../data/lambayequeCoastline'
import { PUERTOS_OFICIALES } from '../data/puertosOficiales'
import type { LambayequeVessel } from '../hooks/useLambayequeVessels'

// Costa y espejo de mar a cargo de la Dirección Regional de Producción de
// Lambayeque. El polígono es ilustrativo (no un límite oficial de la ZEE),
// solo para visualizar la extensión del área de vigilancia sobre el mapa.
// El borde hacia tierra sigue la costa real (LAMBAYEQUE_COASTLINE); el
// borde hacia el mar son dos puntos fijos bien mar adentro.
// El mapa arranca mostrando todo el litoral peruano (no solo Lambayeque):
// las embarcaciones con incidentes confirmados (cargar_incidentes_csv.py)
// operan en alta mar/EEZ a lo largo de toda la costa, no en esta bahía.
const mapCenter: [number, number] = [-10, -78.5]
const mapZoom = 6
const jurisdiction: [number, number][] = [
  ...[...LAMBAYEQUE_COASTLINE].reverse(), // norte -> sur, siguiendo la costa real
  [-7.1, -81.3], // sur, mar adentro
  [-6.35, -81.6], // norte, mar adentro
]

const portLabel = { position: [-6.933, -79.863] as [number, number], label: 'Puerto Eten' }

// Franja de las "5 millas": reservada en exclusiva para pesca artesanal por
// la Ley General de Pesca del Perú (D.L. 25977, art. 9 / su reglamento).
// Se calcula como un buffer real de 5 millas náuticas sobre la costa real
// de arriba, recortado contra el polígono de jurisdicción para no dibujar
// sobre tierra. Ilustrativo (no georreferenciado oficial), igual que el
// polígono de jurisdicción.
function toLonLat([lat, lon]: [number, number]): [number, number] {
  return [lon, lat]
}

const coastlineLine = turf.lineString(LAMBAYEQUE_COASTLINE.map(toLonLat))

function fiveMileZonePositions(): [number, number][][] {
  const jurisdictionPolygon = turf.polygon([[...jurisdiction, jurisdiction[0]].map(toLonLat)])
  const buffered = turf.buffer(coastlineLine, 5, { units: 'nauticalmiles' })
  const clipped = buffered && turf.intersect(turf.featureCollection([buffered, jurisdictionPolygon]))
  if (!clipped) return []

  const rings = clipped.geometry.type === 'Polygon' ? [clipped.geometry.coordinates] : clipped.geometry.coordinates
  return rings.map((polygonCoords) => polygonCoords[0].map(([lon, lat]) => [lat, lon] as [number, number]))
}

const fiveMileZone = fiveMileZonePositions()

// Límite de la Zona Económica Exclusiva peruana (200mn desde la costa). El
// margen es el mismo que MARGEN_FRONTERA_ZEE_NM en server/app/features.py:
// un barco "cerca de la frontera ZEE" es el que, apagando el AIS justo ahí,
// podría cruzar hacia aguas peruanas sin que se note un salto de posición
// grande -- ver server/app/gfw.py:consultar_actividad_con_cache.
const ZEE_NM = 200
const MARGEN_FRONTERA_ZEE_NM = 20

function distanciaCostaNm(lat: number, lon: number): number {
  return turf.pointToLineDistance(turf.point([lon, lat]), coastlineLine, { units: 'nauticalmiles' })
}

// Mismo mapeo que _mapear_tipo en server/app/routes/embarcaciones.py, pero
// mostrando el vesselType crudo de GFW cuando no es "FISHING" en vez de
// colapsarlo todo a "otro" -- acá sí vale la pena mostrar el detalle real.
function etiquetaTipo(vesselType: string | null): string {
  if (!vesselType) return 'Tipo desconocido'
  if (vesselType.toUpperCase() === 'FISHING') return 'Pesca industrial'
  return vesselType
}

const placeLabelIcon = L.divIcon({
  className: '',
  html: `<span style="font-size:13px;font-weight:500;color:#64748b;text-shadow:0 1px 2px rgba(255,255,255,.8);white-space:nowrap;">${portLabel.label}</span>`,
  iconSize: [100, 16],
  iconAnchor: [-6, 8],
})

// Mismo trazo que AnchorIcon (components/icons) -- L.divIcon necesita el SVG
// como string, no como componente React.
const puertoOficialIcon = L.divIcon({
  className: '',
  html: `
    <div style="display:flex;align-items:center;justify-content:center;width:22px;height:22px;border-radius:9999px;background:#1e3a5f;border:2px solid white;box-shadow:0 1px 3px rgba(0,0,0,.4);">
      <svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <circle cx="12" cy="5" r="2" />
        <path d="M12 7v14M5 12H2a10 10 0 0 0 20 0h-3" />
        <path d="M8 9h8" />
      </svg>
    </div>
  `,
  iconSize: [22, 22],
  iconAnchor: [11, 11],
})

function ZoomControls() {
  const map = useMap()
  return (
    <div className="flex flex-col overflow-hidden rounded-lg border border-slate-200 bg-white shadow-sm">
      <button
        type="button"
        aria-label="Acercar"
        onClick={() => map.zoomIn()}
        className="flex h-9 w-9 items-center justify-center text-slate-600 hover:bg-slate-50"
      >
        <PlusIcon className="h-4 w-4" />
      </button>
      <div className="h-px bg-slate-200" />
      <button
        type="button"
        aria-label="Alejar"
        onClick={() => map.zoomOut()}
        className="flex h-9 w-9 items-center justify-center text-slate-600 hover:bg-slate-50"
      >
        <MinusIcon className="h-4 w-4" />
      </button>
    </div>
  )
}

interface UltimoPuerto {
  puerto: string | null
  diasDesdeSalida?: number
  duracionHorasEnPuerto?: number
  // true si el ancla real (Events API) quedó a más de
  // features.UMBRAL_ZONA_NO_AUTORIZADA_NM del puerto oficial más cercano --
  // ver el comentario ahí sobre cómo se calibró ese umbral con datos reales.
  zonaNoAutorizada?: boolean
  puertoOficialMasCercano?: string | null
  distPuertoOficialNm?: number | null
}

// "cargando"/"error" son estados de la consulta; UltimoPuerto|null es el
// resultado ya resuelto (null = todavía no se pidió).
type EstadoUltimoPuerto = UltimoPuerto | 'cargando' | 'error' | null

function formatearDiasDesdeSalida(dias: number): string {
  if (dias <= 0) return 'hoy'
  if (dias === 1) return 'ayer'
  return `hace ${dias} días`
}

interface VesselMarkerProps {
  vessel: LambayequeVessel & { distCostaNm: number }
  conIncidente: boolean
  cercaFronteraZee: boolean
}

/** Componente aparte (no inline en el .map de MapView) porque necesita su
 * propio estado de React para la consulta bajo demanda del último puerto --
 * no tendría sentido pedirla para los ~1000+ barcos de la flota de una, así
 * que se dispara recién al hacer click en ESTE marcador puntual. */
function VesselMarker({ vessel, conIncidente, cercaFronteraZee }: VesselMarkerProps) {
  const [ultimoPuerto, setUltimoPuerto] = useState<EstadoUltimoPuerto>(null)

  async function cargarUltimoPuerto() {
    if (!vessel.vesselId || ultimoPuerto) return // sin vesselId no hay nada que pedir, o ya se pidió
    setUltimoPuerto('cargando')
    try {
      const response = await apiFetch(`/api/embarcaciones/gfw/ultimo-puerto?vesselId=${encodeURIComponent(vessel.vesselId)}`)
      if (!response.ok) throw new Error()
      const data = (await response.json()) as UltimoPuerto
      setUltimoPuerto(data)
    } catch {
      setUltimoPuerto('error')
    }
  }

  const color = conIncidente ? '#dc2626' : cercaFronteraZee ? '#7c3aed' : '#0f766e'

  return (
    <CircleMarker
      center={[vessel.lat, vessel.lon]}
      radius={conIncidente || cercaFronteraZee ? 4 : 3}
      pathOptions={{ color, fillColor: color, fillOpacity: 0.85, weight: 1 }}
      eventHandlers={{ click: cargarUltimoPuerto }}
    >
      {/* Hover: vistazo rápido. Click: descripción completa (Popup abajo). */}
      <Tooltip direction="top" offset={[0, -4]}>
        <strong>{vessel.nombre}</strong>
        {vessel.flag ? ` · ${vessel.flag}` : ''}
      </Tooltip>

      <Popup minWidth={220}>
        <div className="text-xs">
          <p className="text-sm font-bold text-slate-900">{vessel.nombre}</p>

          {(conIncidente || cercaFronteraZee) && (
            <p className="mt-1">
              {conIncidente && (
                <span className="mr-1 inline-block rounded bg-red-100 px-1.5 py-0.5 font-semibold text-red-700">
                  Con incidente confirmado
                </span>
              )}
              {cercaFronteraZee && (
                <span className="inline-block rounded bg-violet-100 px-1.5 py-0.5 font-semibold text-violet-700">
                  Cerca del límite ZEE
                </span>
              )}
            </p>
          )}

          <dl className="mt-2 grid grid-cols-[auto_1fr] gap-x-2 gap-y-0.5 text-slate-600">
            <dt className="font-medium text-slate-400">MMSI</dt>
            <dd>{vessel.mmsi ?? 'No disponible'}</dd>
            <dt className="font-medium text-slate-400">Bandera</dt>
            <dd>{vessel.flag ?? 'Desconocida'}</dd>
            <dt className="font-medium text-slate-400">Tipo</dt>
            <dd>{etiquetaTipo(vessel.vesselType)}</dd>
            <dt className="font-medium text-slate-400">Pesca aparente</dt>
            <dd>{vessel.horas.toFixed(1)} h</dd>
            <dt className="font-medium text-slate-400">Dist. a costa</dt>
            <dd>{vessel.distCostaNm.toFixed(0)} mn</dd>
            <dt className="font-medium text-slate-400">Posición</dt>
            <dd>
              {vessel.lat.toFixed(3)}, {vessel.lon.toFixed(3)}
            </dd>
            <dt className="font-medium text-slate-400">Último puerto</dt>
            <dd>
              {!vessel.vesselId && 'No disponible'}
              {vessel.vesselId && ultimoPuerto === null && 'Toca para consultar'}
              {ultimoPuerto === 'cargando' && 'Consultando GFW…'}
              {ultimoPuerto === 'error' && 'No se pudo consultar'}
              {ultimoPuerto && typeof ultimoPuerto === 'object' && ultimoPuerto.puerto === null && 'Sin visitas registradas'}
              {ultimoPuerto && typeof ultimoPuerto === 'object' && ultimoPuerto.puerto !== null && (
                <>
                  {ultimoPuerto.puerto}
                  {ultimoPuerto.diasDesdeSalida != null && ` · ${formatearDiasDesdeSalida(ultimoPuerto.diasDesdeSalida)}`}
                </>
              )}
            </dd>
          </dl>

          {ultimoPuerto && typeof ultimoPuerto === 'object' && ultimoPuerto.zonaNoAutorizada && (
            <p className="mt-2 rounded bg-amber-100 px-1.5 py-1 font-semibold text-amber-800">
              Zona no autorizada: a {ultimoPuerto.distPuertoOficialNm}mn del puerto oficial más cercano
              {ultimoPuerto.puertoOficialMasCercano ? ` (${ultimoPuerto.puertoOficialMasCercano})` : ''}
            </p>
          )}
        </div>
      </Popup>
    </CircleMarker>
  )
}

interface ZonaCritica {
  id: string
  nombre: string
  poligono: { type: 'Polygon'; coordinates: number[][][] }
}

interface MapViewProps {
  vessels?: LambayequeVessel[]
  mmsiConIncidente?: Set<string>
  /** Zonas marcadas como críticas en la base de datos (tabla "zonas"), con el
   * polígono real que usa el geofencing de "zona_protegida" -- se dibuja en
   * rojo para poder comparar a simple vista contra el contorno ilustrativo
   * de "jurisdiction" (línea azul punteada), que es un dibujo aproximado y
   * NO necesariamente el mismo polígono que delimita las alertas. */
  zonasCriticas?: ZonaCritica[]
  /** Posición exacta de la alerta que se muestra ahora mismo en AlertCard
   * (MonitoringPage) -- se dibuja un único marcador rojo ahí para ubicar la
   * infracción, en vez de pintar de rojo TODAS las posiciones históricas de
   * ese mmsi (el array "vessels" trae una fila por día/celda de GFW, no una
   * por embarcación). */
  alertaPosicion?: { lat: number; lon: number; vessel: string; mmsi: string | null } | null
  children?: ReactNode
}

function poligonoAPosiciones(poligono: ZonaCritica['poligono']): [number, number][][] {
  return poligono.coordinates.map((anillo) => anillo.map(([lon, lat]) => [lat, lon] as [number, number]))
}

export function MapView({ vessels = [], mmsiConIncidente, zonasCriticas = [], alertaPosicion, children }: MapViewProps) {
  // Se calcula una sola vez por cambio de "vessels" (no en cada render): con
  // muchos barcos, turf.pointToLineDistance por marcador en cada render sí
  // se nota.
  const vesselsConDistancia = useMemo(
    () => vessels.map((vessel) => ({ ...vessel, distCostaNm: distanciaCostaNm(vessel.lat, vessel.lon) })),
    [vessels],
  )

  return (
    <div className="relative h-full w-full overflow-hidden">
      <MapContainer
        center={mapCenter}
        zoom={mapZoom}
        zoomControl={false}
        preferCanvas
        className="h-full w-full"
      >
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />

        <Polygon
          positions={jurisdiction}
          pathOptions={{ color: '#0369a1', weight: 1.5, dashArray: '4 4', fillColor: '#38bdf8', fillOpacity: 0.08 }}
        />

        {fiveMileZone.map((ring, index) => (
          <Polygon
            key={index}
            positions={ring}
            pathOptions={{ color: '#b45309', weight: 1.5, fillColor: '#f59e0b', fillOpacity: 0.18 }}
          >
            <Tooltip direction="center" sticky>
              Zona de las 5 millas — reservada para pesca artesanal
            </Tooltip>
          </Polygon>
        ))}

        {zonasCriticas.map((zona) =>
          poligonoAPosiciones(zona.poligono).map((anillo, index) => (
            <Polygon
              key={`${zona.id}-${index}`}
              positions={anillo}
              pathOptions={{ color: '#dc2626', weight: 2, dashArray: '6 4', fillColor: '#dc2626', fillOpacity: 0.05 }}
            >
              <Tooltip direction="center" sticky>
                Zona crítica: {zona.nombre}
              </Tooltip>
            </Polygon>
          )),
        )}

        {/* CircleMarker (canvas) en vez de Marker/divIcon: con miles de barcos
            a escala nacional, un elemento DOM por punto vuelve el mapa lento. */}
        {vesselsConDistancia.map((vessel, index) => {
          const conIncidente = Boolean(vessel.mmsi && mmsiConIncidente?.has(vessel.mmsi))
          const cercaFronteraZee = !conIncidente && Math.abs(vessel.distCostaNm - ZEE_NM) <= MARGEN_FRONTERA_ZEE_NM
          return (
            <VesselMarker
              key={`${vessel.embarcacionId ?? vessel.mmsi ?? 'v'}-${index}`}
              vessel={vessel}
              conIncidente={conIncidente}
              cercaFronteraZee={cercaFronteraZee}
            />
          )
        })}

        {/* Único marcador para la alerta activa (AlertCard): se dibuja
            aparte de "vessels" y con un radio bien mayor + un halo, para que
            se vea de un vistazo dónde ocurrió la infracción sin confundirse
            con el resto de la flota. */}
        {alertaPosicion && (
          <>
            <CircleMarker
              center={[alertaPosicion.lat, alertaPosicion.lon]}
              radius={14}
              pathOptions={{ color: '#dc2626', fillColor: '#dc2626', fillOpacity: 0.15, weight: 1 }}
            />
            <CircleMarker
              center={[alertaPosicion.lat, alertaPosicion.lon]}
              radius={6}
              pathOptions={{ color: '#dc2626', fillColor: '#dc2626', fillOpacity: 0.95, weight: 2 }}
            >
              <Tooltip direction="top" offset={[0, -4]} permanent>
                <strong>{alertaPosicion.vessel}</strong>
                {alertaPosicion.mmsi ? ` · MMSI ${alertaPosicion.mmsi}` : ''}
                <br />
                <span style={{ color: '#dc2626', fontWeight: 600 }}>Alerta de monitoreo activa</span>
              </Tooltip>
            </CircleMarker>
          </>
        )}

        <Marker position={portLabel.position} icon={placeLabelIcon} />

        {/* Puertos oficiales de desembarco (mismos 13 que PUERTOS_PERU en
            server/app/features.py, usados ahí para dist_puerto_mas_cercano_nm) --
            referencia fija en el mapa, no depende de "vessels" ni de ninguna
            consulta a GFW. */}
        {PUERTOS_OFICIALES.map((puerto) => (
          <Marker key={puerto.nombre} position={[puerto.lat, puerto.lon]} icon={puertoOficialIcon}>
            <Tooltip direction="top" offset={[0, -12]}>
              <strong>{puerto.nombre}</strong>
              <br />
              Puerto oficial de desembarco
            </Tooltip>
          </Marker>
        ))}

        <div className="absolute top-4 left-4 z-[1000] flex flex-col gap-2">
          <ZoomControls />
        </div>

        <div className="absolute bottom-4 left-4 z-[1000] rounded-lg border border-slate-200 bg-white px-3 py-2 text-[11px] text-slate-600 shadow-sm">
          <div className="flex items-center gap-1.5">
            <span className="h-2.5 w-2.5 rounded-full bg-[#0f766e]" />
            Embarcación
          </div>
          <div className="mt-1 flex items-center gap-1.5">
            <span className="h-2.5 w-2.5 rounded-full bg-[#7c3aed]" />
            Cerca del límite de las 200mn (ZEE)
          </div>
          <div className="mt-1 flex items-center gap-1.5">
            <span className="h-2.5 w-2.5 rounded-full bg-[#dc2626]" />
            Con incidente confirmado
          </div>
          <div className="mt-1 flex items-center gap-1.5">
            <span className="h-2.5 w-2.5 rounded-full bg-[#1e3a5f]" />
            Puerto oficial de desembarco
          </div>
        </div>
      </MapContainer>

      {children}
    </div>
  )
}
