export type ValidationAccent = 'red' | 'blue'

export interface ValidationItem {
  id: string
  status: 'success'
  timeAgo: string
  source: string
  headline: string
  accent: ValidationAccent
  infractionType: string
  infractionDotColor: 'red' | 'amber'
  detail: { label: string; value: string }
  summary?: string
}

export interface ProcessingItem {
  id: string
  status: 'processing'
  source: string
  stage: string
}

export const validationItems: ValidationItem[] = [
  {
    id: 'val-1',
    status: 'success',
    timeAgo: 'Hace 2 min',
    source: 'thefishingtimes.com',
    headline: 'Autoridades incautan embarcación extranjera por pesca ilegal en el Mar de Grau',
    accent: 'red',
    infractionType: 'Pesca en Zona Prohibida',
    infractionDotColor: 'red',
    detail: { label: 'Embarcación detectada', value: 'M/V OCEAN BREEZE (IMO: 9876543)' },
    summary:
      'La nave fue detectada realizando operaciones de arrastre dentro de las 5 millas, contraviniendo la normativa nacional vigente...',
  },
  {
    id: 'val-2',
    status: 'success',
    timeAgo: 'Hace 15 min',
    source: 'localnoticias.pe',
    headline: 'Reporte de posible contaminación por hidrocarburos cerca al puerto',
    accent: 'blue',
    infractionType: 'Contaminación',
    infractionDotColor: 'amber',
    detail: { label: 'Ubicación estimada', value: 'Puerto del Callao (Aprox)' },
  },
]

export const processingItems: ProcessingItem[] = [
  {
    id: 'proc-1',
    status: 'processing',
    source: 'maritimenews.net/report...',
    stage: 'Extrayendo entidades nombradas (NER)...',
  },
]
