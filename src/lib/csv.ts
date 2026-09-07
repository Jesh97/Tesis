function escaparCelda(valor: string | number): string {
  const texto = String(valor)
  if (/[",\n]/.test(texto)) {
    return `"${texto.replace(/"/g, '""')}"`
  }
  return texto
}

/** Arma un CSV (con BOM para que Excel detecte UTF-8 correctamente) y
 * dispara la descarga en el navegador. */
export function descargarCSV(nombreArchivo: string, filas: (string | number)[][]): void {
  const contenido = filas.map((fila) => fila.map(escaparCelda).join(',')).join('\r\n')
  const blob = new Blob(['﻿' + contenido], { type: 'text/csv;charset=utf-8;' })
  const url = URL.createObjectURL(blob)

  const enlace = document.createElement('a')
  enlace.href = url
  enlace.download = nombreArchivo
  document.body.appendChild(enlace)
  enlace.click()
  document.body.removeChild(enlace)
  URL.revokeObjectURL(url)
}
