import { spawn } from 'node:child_process'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { Router } from 'express'

export const embarcacionesRouter = Router()

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const SYNC_SCRIPT = path.resolve(__dirname, '../../../scripts/sync_lambayeque.py')
const PYTHON_BIN = process.env.PYTHON_BIN || 'python'

// El dataset público de esfuerzo pesquero de GFW tiene varios meses de
// rezago: "hoy - 7 días" casi siempre devuelve 0 resultados. Mientras eso
// no cambie (o no se use un dataset con menor latencia), este es el rango
// que sí devuelve datos de forma confiable — se puede sobrescribir con
// ?desde=&hasta= en la query.
const DEMO_DESDE = '2023-01-01'
const DEMO_HASTA = '2023-01-08'

interface RawVessel {
  embarcacionId: string | null
  nombre: string
  mmsi: string | null
  flag: string | null
  vesselType: string | null
  lat: number
  lon: number
  horas: number
}

// Corre scripts/sync_lambayeque.py --json: consulta GFW en vivo y devuelve
// los barcos sin guardar nada en base de datos (todavía no hay Postgres).
function runSyncScript(desde: string, hasta: string): Promise<RawVessel[]> {
  return new Promise((resolve, reject) => {
    const proc = spawn(PYTHON_BIN, [SYNC_SCRIPT, '--json', '--desde', desde, '--hasta', hasta])
    let stdout = ''
    let stderr = ''
    proc.stdout.on('data', (chunk: Buffer) => {
      stdout += chunk.toString()
    })
    proc.stderr.on('data', (chunk: Buffer) => {
      stderr += chunk.toString()
    })
    proc.on('error', reject)
    proc.on('close', (code) => {
      if (code !== 0) {
        reject(new Error(stderr.trim() || `El script de Python terminó con código ${code}`))
        return
      }
      try {
        resolve(JSON.parse(stdout) as RawVessel[])
      } catch {
        reject(new Error(`No se pudo interpretar la salida del script: ${stdout.slice(0, 300)}`))
      }
    })
  })
}

embarcacionesRouter.get('/gfw/lambayeque', async (req, res) => {
  const desde = typeof req.query.desde === 'string' ? req.query.desde : DEMO_DESDE
  const hasta = typeof req.query.hasta === 'string' ? req.query.hasta : DEMO_HASTA

  try {
    const barcos = await runSyncScript(desde, hasta)
    res.json({ desde, hasta, total: barcos.length, barcos })
  } catch (err) {
    console.error('[embarcaciones/gfw/lambayeque]', err)
    res.status(502).json({ error: err instanceof Error ? err.message : 'Error consultando Global Fishing Watch' })
  }
})
