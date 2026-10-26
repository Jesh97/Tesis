const NOMBRES_MES = ['ene', 'feb', 'mar', 'abr', 'may', 'jun', 'jul', 'ago', 'sep', 'oct', 'nov', 'dic']
const NOMBRES_MES_LARGO = [
  'enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio',
  'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre',
]

/** "2025-07" -> "jul" o, con año, "jul 25". */
export function etiquetaMes(mes: string, conAnio = false): string {
  const [anio, m] = mes.split('-')
  const nombre = NOMBRES_MES[Number(m) - 1]
  return conAnio ? `${nombre} ${anio.slice(2)}` : nombre
}

/** "2025-07" -> "julio 2025". */
export function etiquetaMesLarga(mes: string): string {
  const [anio, m] = mes.split('-')
  return `${NOMBRES_MES_LARGO[Number(m) - 1]} ${anio}`
}

function aClave(fecha: Date): string {
  return `${fecha.getFullYear()}-${String(fecha.getMonth() + 1).padStart(2, '0')}`
}

/** Rango [desde, hasta] (AAAA-MM) de los últimos `cantidad` meses CERRADOS,
 * sin el mes en curso -- igual que rango_por_defecto en
 * server/app/routes/actividad.py. */
export function ultimosMeses(cantidad: number, hoy = new Date()): [string, string] {
  const hasta = new Date(hoy.getFullYear(), hoy.getMonth() - 1, 1)
  const desde = new Date(hasta.getFullYear(), hasta.getMonth() - (cantidad - 1), 1)
  return [aClave(desde), aClave(hasta)]
}
