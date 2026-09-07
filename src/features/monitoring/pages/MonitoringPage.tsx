import { useMemo, useState } from 'react'
import { DashboardLayout } from '../../../components/layout/DashboardLayout'
import { Button } from '../../../components/ui/Button'
import { TextField } from '../../../components/ui/TextField'
import { CalendarIcon } from '../../../components/icons'
import { AlertCard } from '../components/AlertCard'
import { MapView } from '../components/MapView'
import { useActividadSospechosaAlertas } from '../hooks/useActividadSospechosaAlertas'
import { useLambayequeVessels } from '../hooks/useLambayequeVessels'
import { useMmsiConIncidente } from '../hooks/useMmsiConIncidente'
import { useRegistrarIncidente, type TipoAlerta } from '../hooks/useRegistrarIncidente'
import { useZonaProtegidaAlertas } from '../hooks/useZonaProtegidaAlertas'

function formatearCoordenada(valor: number, positivo: string, negativo: string) {
  const abs = Math.abs(valor)
  const grados = Math.floor(abs)
  const minutos = ((abs - grados) * 60).toFixed(0).padStart(2, '0')
  return `${grados}°${minutos}'00" ${valor >= 0 ? positivo : negativo}`
}

// GFW no da datos en tiempo real: su dataset público se completa
// retroactivamente durante semanas/meses. Además, desde que el bbox por
// defecto se acotó a la jurisdicción de Lambayeque (antes era todo el Perú),
// una ventana "relativa a hoy" puede caer en un hueco de cobertura -- se
// verificó en vivo que "hoy-90 a hoy-60" devuelve 0 embarcaciones para
// Lambayeque en la fecha de este cambio. Se usa una ventana fija ya
// verificada con datos reales en vez de una relativa a "hoy" que puede
// romperse silenciosamente. Se puede sobreescribir con los campos de fecha.
const RANGO_POR_DEFECTO = { desde: '2023-06-01', hasta: '2023-09-01' }

export function MonitoringPage() {
  const [rangoAplicado, setRangoAplicado] = useState(RANGO_POR_DEFECTO)
  const [rangoBorrador, setRangoBorrador] = useState(RANGO_POR_DEFECTO)
  const { vessels, error } = useLambayequeVessels(rangoAplicado.desde, rangoAplicado.hasta)
  const { zonas: zonasProtegidas } = useZonaProtegidaAlertas()
  const { zonas: zonasActividad } = useActividadSospechosaAlertas()
  const mmsiConIncidente = useMmsiConIncidente()

  const alertas = useMemo(() => {
    const deZonaProtegida = zonasProtegidas.flatMap((zona) =>
      zona.barcos.map((barco) => ({
        key: `zona:${zona.zonaId}:${barco.mmsi ?? barco.nombre}`,
        tipoAlerta: 'zona_protegida' as TipoAlerta,
        vessel: barco.nombre,
        mmsi: barco.mmsi,
        matricula: barco.mmsi ?? 'Sin MMSI',
        description: `Embarcación detectada dentro de la zona protegida "${zona.zonaNombre}" (${zona.region}).`,
        lat: barco.lat,
        lon: barco.lon,
        latitude: formatearCoordenada(barco.lat, 'N', 'S'),
        longitude: formatearCoordenada(barco.lon, 'E', 'O'),
      })),
    )

    const deActividad = zonasActividad.flatMap((zona) =>
      zona.barcos.map((barco) => {
        const motivos: string[] = []
        if (barco.apagonAis) {
          motivos.push(
            `sin señal AIS por ${barco.apagonAis.diasSinSenal} días (top 10% de la flota de "${zona.zonaNombre}")`,
          )
        }
        if (barco.demoraPuerto) {
          motivos.push(
            `${barco.demoraPuerto.diasLejosDePuerto} días seguidos lejos de puerto (top 10% de la flota)`,
          )
        }
        return {
          key: `actividad:${zona.zonaId}:${barco.mmsi}`,
          tipoAlerta: (barco.apagonAis ? 'apagon_ais' : 'demora_puerto') as TipoAlerta,
          vessel: barco.nombre,
          mmsi: barco.mmsi,
          matricula: barco.mmsi,
          description: `Actividad inusual: ${motivos.join('; ')}.`,
          lat: barco.lat,
          lon: barco.lon,
          latitude: formatearCoordenada(barco.lat, 'N', 'S'),
          longitude: formatearCoordenada(barco.lon, 'E', 'O'),
        }
      }),
    )

    return [...deZonaProtegida, ...deActividad]
  }, [zonasProtegidas, zonasActividad])

  const [descartadas, setDescartadas] = useState<Set<string>>(new Set())
  const [registradas, setRegistradas] = useState<Set<string>>(new Set())
  const { registrar, registrando, error: errorRegistro } = useRegistrarIncidente()
  const visibles = alertas.filter((a) => !descartadas.has(a.key) && !registradas.has(a.key))

  async function handleRegistrar() {
    const alerta = visibles[0]
    if (!alerta) return
    const ok = await registrar({
      tipoAlerta: alerta.tipoAlerta,
      descripcion: alerta.description,
      mmsi: alerta.mmsi,
      vessel: alerta.vessel,
      lat: alerta.lat,
      lon: alerta.lon,
    })
    if (ok) setRegistradas((prev) => new Set(prev).add(alerta.key))
  }

  return (
    <DashboardLayout title="Sistema de Detección de Pesca Ilegal">
      <MapView vessels={vessels} mmsiConIncidente={mmsiConIncidente}>
        <div className="absolute bottom-4 left-4 z-[1000] flex items-end gap-2 rounded-lg border border-slate-200 bg-white p-3 shadow-sm">
          <TextField
            id="monitoreo-desde"
            label="Desde"
            type="date"
            icon={<CalendarIcon className="h-4 w-4" />}
            value={rangoBorrador.desde}
            onChange={(e) => setRangoBorrador((prev) => ({ ...prev, desde: e.target.value }))}
          />
          <TextField
            id="monitoreo-hasta"
            label="Hasta"
            type="date"
            icon={<CalendarIcon className="h-4 w-4" />}
            value={rangoBorrador.hasta}
            onChange={(e) => setRangoBorrador((prev) => ({ ...prev, hasta: e.target.value }))}
          />
          <Button type="button" className="w-auto px-4 py-2.5" onClick={() => setRangoAplicado(rangoBorrador)}>
            Aplicar
          </Button>
        </div>
        {error && (
          <div className="absolute top-4 left-1/2 z-[1000] -translate-x-1/2 rounded-lg bg-white px-3 py-1.5 text-xs text-red-600 shadow-sm">
            No se pudo cargar la posición de embarcaciones: {error}
          </div>
        )}
        {errorRegistro && (
          <div className="absolute top-4 left-1/2 z-[1000] -translate-x-1/2 rounded-lg bg-white px-3 py-1.5 text-xs text-red-600 shadow-sm">
            No se pudo registrar el incidente: {errorRegistro}
          </div>
        )}
        {visibles[0] && (
          <AlertCard
            key={visibles[0].key}
            vessel={visibles[0].vessel}
            matricula={visibles[0].matricula}
            description={visibles[0].description}
            latitude={visibles[0].latitude}
            longitude={visibles[0].longitude}
            onClose={() => setDescartadas((prev) => new Set(prev).add(visibles[0].key))}
            onRegister={registrando ? undefined : handleRegistrar}
          />
        )}
      </MapView>
    </DashboardLayout>
  )
}
