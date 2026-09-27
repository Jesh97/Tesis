export interface PuertoOficial {
  nombre: string
  lat: number
  lon: number
}

// Mismos puertos y coordenadas que PUERTOS_PERU en server/app/features.py
// (ahí se usan para calcular dist_puerto_mas_cercano_nm / demora_puerto) --
// se listan también acá para dibujarlos en el mapa como referencia de
// desembarco oficial.
export const PUERTOS_OFICIALES: PuertoOficial[] = [
  { nombre: 'Bayóvar', lat: -5.83, lon: -81.11 },
  { nombre: 'Callao', lat: -12.05, lon: -77.15 },
  { nombre: 'Chancay', lat: -11.57, lon: -77.27 },
  { nombre: 'Chimbote', lat: -9.09, lon: -78.6 },
  { nombre: 'Huacho', lat: -11.11, lon: -77.62 },
  { nombre: 'Huarmey', lat: -10.07, lon: -78.15 },
  { nombre: 'Ilo', lat: -17.65, lon: -71.34 },
  { nombre: 'Matarani', lat: -17.0, lon: -72.1 },
  { nombre: 'Pisco', lat: -13.71, lon: -76.2 },
  { nombre: 'Puerto Chicama', lat: -7.7, lon: -79.44 },
  { nombre: 'San Juan de Marcona', lat: -15.35, lon: -75.16 },
  { nombre: 'San Nicolás', lat: -15.27, lon: -75.24 },
  { nombre: 'Talara', lat: -4.58, lon: -81.27 },
]
