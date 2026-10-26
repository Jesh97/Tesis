import { describe, expect, it } from 'vitest'
import { etiquetaMes, etiquetaMesLarga, ultimosMeses } from './meses'

describe('meses', () => {
  it('arma etiquetas cortas y largas', () => {
    expect(etiquetaMes('2025-07')).toBe('jul')
    expect(etiquetaMes('2025-01', true)).toBe('ene 25')
    expect(etiquetaMesLarga('2025-11')).toBe('noviembre 2025')
  })

  it('ultimosMeses excluye el mes en curso, igual que el backend', () => {
    expect(ultimosMeses(24, new Date(2026, 9, 24))).toEqual(['2024-10', '2026-09'])
    expect(ultimosMeses(12, new Date(2026, 0, 5))).toEqual(['2025-01', '2025-12'])
  })
})
