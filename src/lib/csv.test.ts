import { afterEach, describe, expect, it, vi } from 'vitest'
import { descargarCSV } from './csv'

const BlobOriginal = globalThis.Blob

function espiarBlob(): { contenido: () => Promise<string>; primerosBytes: () => Promise<number[]> } {
  let capturado: BlobPart[] = []
  // function (no arrow function): vitest necesita poder invocar el mock con
  // `new`, igual que descargarCSV hace con `new Blob(...)`.
  vi.spyOn(globalThis, 'Blob').mockImplementation(function (parts?: BlobPart[], opts?: BlobPropertyBag) {
    capturado = parts ?? []
    return new BlobOriginal(parts, opts)
  } as unknown as typeof Blob)
  vi.spyOn(URL, 'createObjectURL').mockReturnValue('blob:mock-url')
  vi.spyOn(URL, 'revokeObjectURL').mockImplementation(() => {})
  return {
    // Blob.text() decodifica como UTF-8 y, por spec (TextDecoder con
    // ignoreBOM=false, el default), descarta el BOM inicial si lo
    // encuentra -- por eso el BOM se verifica aparte, a nivel de bytes.
    contenido: () => new BlobOriginal(capturado).text(),
    primerosBytes: async () => Array.from(new Uint8Array(await new BlobOriginal(capturado).arrayBuffer()).slice(0, 3)),
  }
}

afterEach(() => {
  vi.restoreAllMocks()
})

describe('descargarCSV', () => {
  it('separa las celdas con coma y las filas con CRLF', async () => {
    const blob = espiarBlob()

    descargarCSV('reporte.csv', [
      ['Nombre', 'Cantidad'],
      ['Ana', 3],
    ])

    expect(await blob.contenido()).toBe('Nombre,Cantidad\r\nAna,3')
  })

  it('envuelve entre comillas y escapa comillas internas cuando la celda tiene coma, comillas o salto de línea', async () => {
    const blob = espiarBlob()

    descargarCSV('reporte.csv', [['Dice "hola", chau\nfin', 'sin problema']])

    expect(await blob.contenido()).toBe('"Dice ""hola"", chau\nfin",sin problema')
  })

  it('antepone el BOM UTF-8 a los bytes del archivo, para que Excel detecte la codificación', async () => {
    const blob = espiarBlob()

    descargarCSV('reporte.csv', [['x']])

    expect(await blob.primerosBytes()).toEqual([0xef, 0xbb, 0xbf])
  })

  it('dispara la descarga con el nombre de archivo indicado', () => {
    espiarBlob()
    const clickSpy = vi.fn()
    const crearElemento = document.createElement.bind(document)
    vi.spyOn(document, 'createElement').mockImplementation((tag: string) => {
      const el = crearElemento(tag)
      if (tag === 'a') (el as HTMLAnchorElement).click = clickSpy
      return el
    })

    descargarCSV('mi-reporte.csv', [['a']])

    expect(clickSpy).toHaveBeenCalledOnce()
  })
})
