export type IncidentSeverity = 'alto' | 'medio' | 'bajo'

export interface Incident {
  id: string
  vessel: string
  vesselCode: string
  infraction: string
  /** Fecha ya formateada para mostrar en la tabla (ver formatearFecha en useIncidentes.ts). */
  dateTime: string
  /** Fecha cruda en ISO, para exportar a CSV sin perder precisión. */
  dateTimeIso: string
  severity: IncidentSeverity
  estado: 'sospechoso' | 'confirmado' | 'descartado'
  lat: number | null
  lon: number | null
}
