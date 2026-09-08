import { useMemo, useState } from 'react'
import { DashboardLayout } from '../../../components/layout/DashboardLayout'
import { ReportarIncidenteModal } from '../../incidents/components/ReportarIncidenteModal'
import { useZonas } from '../../zones/hooks/useZonas'
import { AlertCard } from '../components/AlertCard'
import { MapView } from '../components/MapView'
import { useActividadSospechosaAlertas } from '../hooks/useActividadSospechosaAlertas'
import { useLambayequeVessels } from '../hooks/useLambayequeVessels'
import { useMmsiConIncidente } from '../hooks/useMmsiConIncidente'
import type { TipoAlerta } from '../types'
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
// verificada con datos reales. El filtro de fechas en la UI se quitó
// temporalmente; para cambiar el rango, editar esta constante.
const RANGO_POR_DEFECTO = { desde: '2023-06-01', hasta: '2023-09-01' }

// Mismo mapeo que NOMBRE_TIPO_INFRACCION_POR_ALERTA en
// server/app/routes/incidentes.py -- se usa acá para preseleccionar el tipo
// de infracción en el formulario de "Registrar incidente" cuando viene de
// una alerta del mapa (el analista igual puede cambiarlo antes de enviar).
const NOMBRE_TIPO_INFRACCION_POR_ALERTA: Record<TipoAlerta, string> = {
  zona_protegida: 'Pesca en Zona Prohibida',
  apagon_ais: 'Pérdida de Señal AIS',
  demora_puerto: 'Encuentro Sospechoso en Alta Mar',
}

export function MonitoringPage() {
  const { vessels, error } = useLambayequeVessels(RANGO_POR_DEFECTO.desde, RANGO_POR_DEFECTO.hasta)
  const { zonas: zonasProtegidas } = useZonaProtegidaAlertas()
  const { zonas: zonasActividad } = useActividadSospechosaAlertas()
  const mmsiConIncidente = useMmsiConIncidente()
  const { zonas: todasLasZonas } = useZonas()
  const zonasCriticas = useMemo(
    () => todasLasZonas.filter((z) => z.es_critica && z.poligono).map((z) => ({ id: z.id, nombre: z.nombre, poligono: z.poligono! })),
    [todasLasZonas],
  )

  const alertas = useMemo(() => {
    const deZonaProtegida = zonasProtegidas.flatMap((zona) =>
      zona.barcos.map((barco) => ({
        key: `zona:${zona.zonaId}:${barco.mmsi ?? barco.nombre}`,
        tipoAlerta: 'zona_protegida' as TipoAlerta,
        vessel: barco.nombre,
        mmsi: barco.mmsi,
        flag: barco.flag,
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
          flag: barco.flag,
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
  const [alertaAReportar, setAlertaAReportar] = useState<(typeof alertas)[number] | null>(null)
  const visibles = alertas.filter((a) => !descartadas.has(a.key) && !registradas.has(a.key))

  return (
    <DashboardLayout title="Sistema de Detección de Pesca Ilegal">
      <MapView
        vessels={vessels}
        mmsiConIncidente={mmsiConIncidente}
        zonasCriticas={zonasCriticas}
        alertaPosicion={
          visibles[0]
            ? { lat: visibles[0].lat, lon: visibles[0].lon, vessel: visibles[0].vessel, mmsi: visibles[0].mmsi }
            : null
        }
      >
        {error && (
          <div className="absolute top-4 left-1/2 z-[1000] -translate-x-1/2 rounded-lg bg-white px-3 py-1.5 text-xs text-red-600 shadow-sm">
            No se pudo cargar la posición de embarcaciones: {error}
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
            onRegister={() => setAlertaAReportar(visibles[0])}
          />
        )}
      </MapView>
      {alertaAReportar && (
        <ReportarIncidenteModal
          onClose={() => setAlertaAReportar(null)}
          onRegistrado={() => {
            setRegistradas((prev) => new Set(prev).add(alertaAReportar.key))
          }}
          datosIniciales={{
            vessel: alertaAReportar.vessel,
            mmsi: alertaAReportar.mmsi ?? undefined,
            descripcion: alertaAReportar.description,
            lat: alertaAReportar.lat,
            lon: alertaAReportar.lon,
            flag: alertaAReportar.flag,
            tipoInfraccionNombre: NOMBRE_TIPO_INFRACCION_POR_ALERTA[alertaAReportar.tipoAlerta],
          }}
        />
      )}
    </DashboardLayout>
  )
}
