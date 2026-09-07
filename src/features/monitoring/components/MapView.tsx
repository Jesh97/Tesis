import type { ReactNode } from 'react'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import { CircleMarker, MapContainer, Marker, Polygon, TileLayer, Tooltip, useMap } from 'react-leaflet'
import * as turf from '@turf/turf'
import { FilterIcon, LayersIcon, MinusIcon, PlusIcon } from '../../../components/icons'
import { LAMBAYEQUE_COASTLINE } from '../data/lambayequeCoastline'
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

function fiveMileZonePositions(): [number, number][][] {
  const coastline = turf.lineString(LAMBAYEQUE_COASTLINE.map(toLonLat))
  const jurisdictionPolygon = turf.polygon([[...jurisdiction, jurisdiction[0]].map(toLonLat)])
  const buffered = turf.buffer(coastline, 5, { units: 'nauticalmiles' })
  const clipped = buffered && turf.intersect(turf.featureCollection([buffered, jurisdictionPolygon]))
  if (!clipped) return []

  const rings = clipped.geometry.type === 'Polygon' ? [clipped.geometry.coordinates] : clipped.geometry.coordinates
  return rings.map((polygonCoords) => polygonCoords[0].map(([lon, lat]) => [lat, lon] as [number, number]))
}

const fiveMileZone = fiveMileZonePositions()

const placeLabelIcon = L.divIcon({
  className: '',
  html: `<span style="font-size:13px;font-weight:500;color:#64748b;text-shadow:0 1px 2px rgba(255,255,255,.8);white-space:nowrap;">${portLabel.label}</span>`,
  iconSize: [100, 16],
  iconAnchor: [-6, 8],
})

interface MapControlButtonProps {
  children: ReactNode
  label: string
}

function MapControlButton({ children, label }: MapControlButtonProps) {
  return (
    <button
      aria-label={label}
      className="flex h-9 w-9 items-center justify-center rounded-lg border border-slate-200 bg-white text-slate-600 shadow-sm hover:bg-slate-50"
    >
      {children}
    </button>
  )
}

function ZoomControls() {
  const map = useMap()
  return (
    <div className="flex flex-col overflow-hidden rounded-lg border border-slate-200 bg-white shadow-sm">
      <button
        aria-label="Acercar"
        onClick={() => map.zoomIn()}
        className="flex h-9 w-9 items-center justify-center text-slate-600 hover:bg-slate-50"
      >
        <PlusIcon className="h-4 w-4" />
      </button>
      <div className="h-px bg-slate-200" />
      <button
        aria-label="Alejar"
        onClick={() => map.zoomOut()}
        className="flex h-9 w-9 items-center justify-center text-slate-600 hover:bg-slate-50"
      >
        <MinusIcon className="h-4 w-4" />
      </button>
    </div>
  )
}

interface MapViewProps {
  vessels?: LambayequeVessel[]
  mmsiConIncidente?: Set<string>
  children?: ReactNode
}

export function MapView({ vessels = [], mmsiConIncidente, children }: MapViewProps) {
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

        {/* CircleMarker (canvas) en vez de Marker/divIcon: con miles de barcos
            a escala nacional, un elemento DOM por punto vuelve el mapa lento. */}
        {vessels.map((vessel, index) => {
          const conIncidente = Boolean(vessel.mmsi && mmsiConIncidente?.has(vessel.mmsi))
          const color = conIncidente ? '#dc2626' : '#0f766e'
          return (
            <CircleMarker
              key={`${vessel.embarcacionId ?? vessel.mmsi ?? 'v'}-${index}`}
              center={[vessel.lat, vessel.lon]}
              radius={conIncidente ? 4 : 3}
              pathOptions={{ color, fillColor: color, fillOpacity: 0.85, weight: 1 }}
            >
              <Tooltip direction="top" offset={[0, -4]}>
                <strong>{vessel.nombre}</strong>
                {vessel.mmsi ? ` · MMSI ${vessel.mmsi}` : ''}
                <br />
                {vessel.horas.toFixed(1)} h de pesca aparente
                {conIncidente && (
                  <>
                    <br />
                    <span style={{ color: '#dc2626', fontWeight: 600 }}>Con incidente confirmado</span>
                  </>
                )}
              </Tooltip>
            </CircleMarker>
          )
        })}

        <Marker position={portLabel.position} icon={placeLabelIcon} />

        <div className="absolute top-4 left-4 z-[1000] flex flex-col gap-2">
          <ZoomControls />
          <MapControlButton label="Capas">
            <LayersIcon className="h-4 w-4" />
          </MapControlButton>
          <MapControlButton label="Filtros">
            <FilterIcon className="h-4 w-4" />
          </MapControlButton>
        </div>
      </MapContainer>

      {children}
    </div>
  )
}
