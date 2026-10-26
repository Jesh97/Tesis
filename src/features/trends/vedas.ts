// Vedas y suspensiones de PRODUCE que alcanzaron al mar de Lambayeque
// (LAMBAYEQUE_BBOX en scripts/sync_lambayeque.py: 06°00'S - 07°12'S) dentro
// del rango del Histórico. Es un calendario regulatorio fijo, por eso vive
// acá y no en la BD: si PRODUCE publica una nueva norma, se agrega a mano.
//
// Fechas: `desde` es el primer día de veda y `hasta` el día (a las 00:00) en
// que deja de regir, o null si sigue vigente. Para anchoveta la veda es el
// tiempo ENTRE temporadas de pesca de la zona Norte-Centro (extremo norte a
// 16°00'S), así que `desde` = conclusión de una temporada y `hasta` = inicio
// de la siguiente.
//
// No se incluye la merluza: sus vedas reproductivas recientes (RM
// 078-2025 y 106-2025-PRODUCE) fueron al norte de los 06°00'S, fuera del bbox.

export type RecursoVeda = 'anchoveta' | 'perico'

export interface PeriodoVeda {
  recurso: RecursoVeda
  desde: string
  hasta: string | null
  motivo: string
  norma: string
  /** Franja desde la costa (mn) a la que se limita la medida; sin valor =
   * toda la jurisdicción mar adentro. */
  millas?: number
  /** [norte, sur] en grados (negativos = sur) a los que se limita la
   * medida; sin valor = toda la jurisdicción de norte a sur. Las normas
   * delimitan cada zona así: paralelos + millas desde la costa. */
  latitudes?: [number, number]
}

export const NOMBRE_RECURSO: Record<RecursoVeda, string> = {
  anchoveta: 'Anchoveta (CHI, Norte-Centro)',
  perico: 'Perico o dorado',
}

export const COLOR_VEDA: Record<RecursoVeda, string> = {
  anchoveta: '#d97706',
  perico: '#0d9488',
}

export const VEDAS_LAMBAYEQUE: PeriodoVeda[] = [
  // --- Anchoveta: entre temporadas ---
  {
    recurso: 'anchoveta',
    desde: '2023-01-01',
    hasta: '2023-10-26',
    motivo: 'Sin primera temporada 2023 por El Niño costero',
    norma: 'Inicio 2da temporada 2023: RM 358-2023-PRODUCE',
  },
  {
    recurso: 'anchoveta',
    desde: '2024-01-13',
    hasta: '2024-04-16',
    motivo: 'Veda entre la 2da temporada 2023 y la 1ra 2024',
    norma: 'RM 008-2024-PRODUCE (cierre) · RM 118-2024-PRODUCE (inicio)',
  },
  {
    recurso: 'anchoveta',
    desde: '2024-07-18',
    hasta: '2024-11-01',
    motivo: 'Veda entre la 1ra y la 2da temporada 2024',
    norma: 'RM 289-2024-PRODUCE (cierre) · RM 419-2024-PRODUCE (inicio)',
  },
  {
    recurso: 'anchoveta',
    desde: '2025-01-23',
    hasta: '2025-04-22',
    motivo: 'Veda reproductiva (cierre anticipado por desove)',
    norma: 'RM 017-2025-PRODUCE (cierre) · RM 148-2025-PRODUCE (inicio)',
  },
  {
    recurso: 'anchoveta',
    desde: '2025-07-24',
    hasta: '2025-11-07',
    motivo: 'Cierre anticipado por captura de juveniles',
    norma: 'RD 120-2025-PRODUCE/DGSFS-PA (cierre) · RM 368-2025-PRODUCE (inicio)',
  },
  {
    recurso: 'anchoveta',
    desde: '2026-02-01',
    hasta: '2026-04-01',
    motivo: 'Veda entre la 2da temporada 2025 y la 1ra 2026',
    norma: 'Cierre 2da temporada 2025 · RM 085-2026-PRODUCE (inicio)',
  },
  // Dentro de Lambayeque solo alcanza el extremo sur (07°00'S - 07°12'S,
  // frente a Puerto Eten).
  {
    recurso: 'anchoveta',
    desde: '2026-04-22',
    hasta: '2026-05-07',
    motivo: "Suspensión por juveniles entre 07°00'S y 09°30'S (Eten - Chimbote)",
    norma: 'RD 00044-2026-PRODUCE/DGSFS-PA',
    millas: 10,
    latitudes: [-7.0, -9.5],
  },
  {
    recurso: 'anchoveta',
    desde: '2026-05-12',
    hasta: '2026-06-11',
    motivo: 'Suspensión por juveniles entre 06°S y 14°S (15 días + ampliación de 15)',
    norma: 'RD 00052-2026 y RD 00060-2026-PRODUCE/DGSFS-PA',
    millas: 30,
    latitudes: [-6.0, -14.0],
  },
  {
    recurso: 'anchoveta',
    desde: '2026-06-11',
    hasta: '2026-08-21',
    motivo: 'Suspensión de la 1ra temporada 2026 por mar cálido y juveniles',
    norma: 'RM 162-2026-PRODUCE',
  },
  {
    recurso: 'anchoveta',
    desde: '2026-08-21',
    hasta: null,
    motivo: 'Fin de la 1ra temporada 2026; PRODUCE descartó la 2da temporada',
    norma: 'RM 285-2026-PRODUCE (cierre)',
  },
  // --- Perico: veda anual del 1 de mayo al 30 de septiembre ---
  ...[2023, 2024, 2025, 2026].map(
    (anio): PeriodoVeda => ({
      recurso: 'perico',
      desde: `${anio}-05-01`,
      hasta: `${anio}-10-01`,
      motivo: 'Veda anual (temporada de pesca: 1 oct - 30 abr)',
      norma: 'RM 245-2014-PRODUCE',
    }),
  ),
]

export interface VedaDelMes extends PeriodoVeda {
  /** Días del mes cubiertos por la veda. */
  dias: number
  mesCompleto: boolean
}

const MS_DIA = 24 * 60 * 60 * 1000

function aUtc(fecha: string): number {
  const [anio, mes, dia] = fecha.split('-').map(Number)
  return Date.UTC(anio, mes - 1, dia)
}

/** Vedas que rigieron al menos un día en el mes `mes` (AAAA-MM). */
export function vedasDelMes(mes: string, vedas: PeriodoVeda[] = VEDAS_LAMBAYEQUE): VedaDelMes[] {
  const [anio, numero] = mes.split('-').map(Number)
  const inicioMes = Date.UTC(anio, numero - 1, 1)
  const finMes = Date.UTC(anio, numero, 1)
  const diasMes = (finMes - inicioMes) / MS_DIA

  return vedas.flatMap((veda) => {
    const desde = Math.max(aUtc(veda.desde), inicioMes)
    const hasta = Math.min(veda.hasta ? aUtc(veda.hasta) : Infinity, finMes)
    if (hasta <= desde) return []
    const dias = Math.round((hasta - desde) / MS_DIA)
    return [{ ...veda, dias, mesCompleto: dias === diasMes }]
  })
}

/** Días de veda de un recurso en el mes (suma de sus períodos). */
export function diasDeVeda(mes: string, recurso: RecursoVeda): number {
  return vedasDelMes(mes)
    .filter((v) => v.recurso === recurso)
    .reduce((total, v) => total + v.dias, 0)
}
