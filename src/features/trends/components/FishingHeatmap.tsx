import { useEffect } from 'react'
import 'leaflet/dist/leaflet.css'
import { MapContainer, Rectangle, TileLayer, Tooltip, useMap } from 'react-leaflet'
import { etiquetaMesLarga } from '../meses'

// Rampa secuencial de un solo tono (azul, claro -> oscuro): más horas de
// pesca aparente = más oscuro. Mismo azul que la serie 1 de los gráficos.
const RAMPA = ['#cde2fb', '#9ec5f4', '#6da7ec', '#3987e5', '#256abf', '#184f95', '#0d366b']

// Celdas LOW de la 4Wings API: ~0.1° por lado (ver
// gfw_client.obtener_esfuerzo_mensual). Se dibujan centradas en la
// coordenada que devuelve GFW -- la posición es aproximada a ±5km.
const MEDIO_LADO = 0.05

// Bbox de Lambayeque (LAMBAYEQUE_BBOX en scripts/sync_lambayeque.py), como
// [[lat_min, lon_min], [lat_max, lon_max]] para Leaflet.
const BBOX_LAMBAYEQUE: [[number, number], [number, number]] = [
  [-7.2, -84.5],
  [-6.0, -79.6],
]

/** Encuadra el mapa en las celdas con pesca del mes (casi siempre pegadas a
 * la costa) en vez de todo el bbox, que llega hasta las 200mn y dejaba la
 * zona de pesca chiquita en una esquina. Sin celdas, muestra el bbox entero. */
function EncuadrarCeldas({ celdas }: { celdas: [number, number, number][] }) {
  const map = useMap()
  useEffect(() => {
    if (celdas.length === 0) {
      map.fitBounds(BBOX_LAMBAYEQUE)
      return
    }
    const lats = celdas.map((c) => c[0])
    const lons = celdas.map((c) => c[1])
    map.fitBounds(
      [
        [Math.min(...lats) - MEDIO_LADO, Math.min(...lons) - MEDIO_LADO],
        [Math.max(...lats) + MEDIO_LADO, Math.max(...lons) + MEDIO_LADO],
      ],
      { padding: [24, 24], maxZoom: 9 },
    )
  }, [map, celdas])
  return null
}

/** Escala logarítmica: unas pocas celdas cerca de la costa concentran
 * cientos de horas y con escala lineal todo el resto quedaba en el tono más
 * claro, sin poder distinguir nada. */
function indiceRampa(horas: number, maximo: number): number {
  if (maximo <= 0) return 0
  const t = Math.log1p(horas) / Math.log1p(maximo)
  return Math.min(RAMPA.length - 1, Math.floor(t * RAMPA.length))
}

interface FishingHeatmapProps {
  mes: string
  celdas: [number, number, number][]
}

export function FishingHeatmap({ mes, celdas }: FishingHeatmapProps) {
  const maximo = Math.max(0, ...celdas.map((c) => c[2]))

  return (
    <div className="rounded-xl border border-slate-200 bg-white p-5">
      <h2 className="text-sm font-semibold text-slate-900">
        Dónde se pescó · <span className="capitalize">{etiquetaMesLarga(mes)}</span>
      </h2>
      <p className="mt-0.5 text-xs text-slate-500">
        Horas de pesca aparente por celda de ~11 km. Haz click en un mes de los gráficos para cambiarlo.
      </p>

      <div className="relative mt-4 h-80 overflow-hidden rounded-lg border border-slate-100">
        <MapContainer bounds={BBOX_LAMBAYEQUE} scrollWheelZoom={false} className="h-full w-full">
          <EncuadrarCeldas celdas={celdas} />
          <TileLayer
            attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
            url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          />
          {celdas.map(([lat, lon, horas]) => (
            <Rectangle
              key={`${lat},${lon}`}
              bounds={[
                [lat - MEDIO_LADO, lon - MEDIO_LADO],
                [lat + MEDIO_LADO, lon + MEDIO_LADO],
              ]}
              pathOptions={{ stroke: false, fillColor: RAMPA[indiceRampa(horas, maximo)], fillOpacity: 0.85 }}
            >
              <Tooltip>
                {horas.toLocaleString('es-PE', { maximumFractionDigits: 1 })} h de pesca aparente
              </Tooltip>
            </Rectangle>
          ))}
        </MapContainer>

        {celdas.length === 0 && (
          <div className="pointer-events-none absolute inset-0 z-[400] flex items-center justify-center bg-white/60">
            <p className="rounded-lg bg-white px-3 py-2 text-sm text-slate-500 shadow-sm">
              Sin pesca aparente registrada este mes.
            </p>
          </div>
        )}
      </div>

      {celdas.length > 0 && (
        <div className="mt-3 flex items-center gap-2 text-[11px] text-slate-500">
          <span>Menos</span>
          <div className="flex">
            {RAMPA.map((color) => (
              <span key={color} className="h-2.5 w-6" style={{ backgroundColor: color }} />
            ))}
          </div>
          <span>Más ({maximo.toLocaleString('es-PE', { maximumFractionDigits: 0 })} h máx. en una celda)</span>
        </div>
      )}
    </div>
  )
}
