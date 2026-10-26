import { describe, expect, it } from 'vitest'
import { diasDeVeda, vedasDelMes } from './vedas'

describe('vedas', () => {
  it('cuenta los días de veda dentro del mes (hasta es exclusivo)', () => {
    // Veda anchoveta 13-ene-2024 -> 16-abr-2024.
    expect(diasDeVeda('2024-01', 'anchoveta')).toBe(19)
    expect(diasDeVeda('2024-02', 'anchoveta')).toBe(29)
    expect(diasDeVeda('2024-04', 'anchoveta')).toBe(15)
    expect(diasDeVeda('2024-05', 'anchoveta')).toBe(0)
  })

  it('marca mes completo solo si cubre todos los días', () => {
    const [anchoveta] = vedasDelMes('2024-03').filter((v) => v.recurso === 'anchoveta')
    expect(anchoveta.mesCompleto).toBe(true)
    expect(vedasDelMes('2024-04').find((v) => v.recurso === 'anchoveta')?.mesCompleto).toBe(false)
  })

  it('incluye la veda anual del perico de mayo a septiembre', () => {
    expect(diasDeVeda('2025-04', 'perico')).toBe(0)
    expect(diasDeVeda('2025-05', 'perico')).toBe(31)
    expect(diasDeVeda('2025-09', 'perico')).toBe(30)
    expect(diasDeVeda('2025-10', 'perico')).toBe(0)
  })

  it('suma suspensiones del mismo mes y deja abierta la veda vigente', () => {
    // 1-6 may (RD 044, hasta el 7 exclusivo) + 12-31 may (RD 052/060).
    expect(diasDeVeda('2026-05', 'anchoveta')).toBe(26)
    expect(diasDeVeda('2026-09', 'anchoveta')).toBe(30)
  })
})
