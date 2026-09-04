import { useState } from 'react'
import { DashboardLayout } from '../../../components/layout/DashboardLayout'
import { AlertCard } from '../components/AlertCard'
import { MapView } from '../components/MapView'
import { useLambayequeVessels } from '../hooks/useLambayequeVessels'

export function MonitoringPage() {
  const [alertVisible, setAlertVisible] = useState(true)
  const { vessels, error } = useLambayequeVessels()

  return (
    <DashboardLayout title="Sistema de Detección de Pesca Ilegal">
      <MapView vessels={vessels}>
        {error && (
          <div className="absolute top-4 left-1/2 z-[1000] -translate-x-1/2 rounded-lg bg-white px-3 py-1.5 text-xs text-red-600 shadow-sm">
            No se pudo cargar la posición de embarcaciones: {error}
          </div>
        )}
        {alertVisible && (
          <AlertCard
            vessel="T/N ALBATROS"
            matricula="PL-4920-ZM"
            description="Posible incursión en Zona Económica Exclusiva sin autorización registrada."
            speedKnots={14.2}
            headingDegrees={340}
            heading="NNO"
            latitude={'6°55\'12" S'}
            longitude={'80°33\'00" W'}
            onClose={() => setAlertVisible(false)}
          />
        )}
      </MapView>
    </DashboardLayout>
  )
}
