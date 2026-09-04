export interface StatSummary {
  label: string
  value: string
  trend?: string
}

export const statSummaries: StatSummary[] = [
  { label: 'Total Incidentes', value: '1,245', trend: '+12%' },
  { label: 'Embarc. Capturadas', value: '84', trend: '+5%' },
  { label: 'Alertas Procesadas', value: '3,890' },
  { label: 'Zonas Críticas', value: '12' },
]

export const monthlyIncidents = [38, 52, 46, 61, 55, 40, 33, 58, 70, 64, 78, 92]

export interface InfractionType {
  label: string
  percentage: number
  color: string
}

export const infractionTypes: InfractionType[] = [
  { label: 'Pesca en Zona Prohibida', percentage: 45, color: 'bg-red-500' },
  { label: 'Falta de Permiso', percentage: 30, color: 'bg-slate-900' },
  { label: 'Transbordo Ilegal', percentage: 15, color: 'bg-amber-400' },
  { label: 'Contaminación', percentage: 10, color: 'bg-slate-300' },
]

export interface TopZone {
  rank: number
  name: string
  region: string
  incidents: number
}

export const topZones: TopZone[] = [
  { rank: 1, name: 'Paita', region: 'Norte', incidents: 412 },
  { rank: 2, name: 'Chimbote', region: 'Centro-Norte', incidents: 305 },
  { rank: 3, name: 'Callao', region: 'Centro', incidents: 189 },
]
