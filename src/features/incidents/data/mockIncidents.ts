export type IncidentSeverity = 'alto' | 'medio' | 'bajo'

export interface Incident {
  id: string
  vessel: string
  vesselCode: string
  infraction: string
  dateTime: string
  severity: IncidentSeverity
}

export const mockIncidents: Incident[] = [
  {
    id: 'INC-2023-089',
    vessel: 'Marde Plata II',
    vesselCode: 'MMSI: 720048123',
    infraction: 'Pesca en Zona Protegida (Reserva de Paracas)',
    dateTime: '24 Oct 2023, 14:32',
    severity: 'alto',
  },
  {
    id: 'INC-2023-088',
    vessel: 'Poseidón V',
    vesselCode: 'MMSI: 720098441',
    infraction: 'Pérdida de señal AIS (> 4 horas)',
    dateTime: '24 Oct 2023, 11:15',
    severity: 'medio',
  },
  {
    id: 'INC-2023-087',
    vessel: 'San Pedro Pescador',
    vesselCode: 'MAT: PT-1123A-CM',
    infraction: 'Velocidad inusual en zona de tránsito',
    dateTime: '23 Oct 2023, 22:45',
    severity: 'bajo',
  },
  {
    id: 'INC-2023-086',
    vessel: 'Lobo de Mar IX',
    vesselCode: 'MMSI: 720112990',
    infraction: 'Encuentro sospechoso en alta mar (Transbordo)',
    dateTime: '23 Oct 2023, 19:10',
    severity: 'alto',
  },
]

export const totalIncidents = 124
