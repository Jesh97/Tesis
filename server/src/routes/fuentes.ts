import { spawn } from 'node:child_process'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { Router } from 'express'
import { pool } from '../db.js'

export const fuentesRouter = Router()

const URL_LIMIT = 10 // mismo límite que muestra WebAnalyzerCard en el frontend

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const ANALYZE_SCRIPT = path.resolve(__dirname, '../../../scripts/analyze_news.py')
const PYTHON_BIN = process.env.PYTHON_BIN || 'python'

// Lanza scripts/analyze_news.py (fetch + readability + Claude) como
// subproceso, pasándole el lote por stdin. No se espera a que termine: el
// cliente hace polling vía GET /api/fuentes o GET /api/sugerencias.
function runAnalyzeNewsScript(fuentes: { id: string; url: string }[]): void {
  const proc = spawn(PYTHON_BIN, [ANALYZE_SCRIPT], { stdio: ['pipe', 'pipe', 'pipe'] })
  proc.stdin.write(JSON.stringify(fuentes))
  proc.stdin.end()
  proc.stdout.on('data', (chunk: Buffer) => console.log(`[analyze_news] ${chunk.toString().trim()}`))
  proc.stderr.on('data', (chunk: Buffer) => console.error(`[analyze_news] ${chunk.toString().trim()}`))
  proc.on('error', (err) => console.error('[analyze_news] no se pudo iniciar el proceso Python:', err))
}

fuentesRouter.post('/analizar', async (req, res) => {
  const urls: unknown = req.body?.urls
  if (!Array.isArray(urls) || urls.length === 0) {
    res.status(400).json({ error: 'Se requiere un arreglo "urls" con al menos un elemento' })
    return
  }
  if (urls.length > URL_LIMIT) {
    res.status(400).json({ error: `Máximo ${URL_LIMIT} URLs por lote` })
    return
  }

  const creados: { id: string; url: string }[] = []
  for (const rawUrl of urls) {
    if (typeof rawUrl !== 'string') continue

    let dominio: string
    try {
      dominio = new URL(rawUrl).hostname.replace(/^www\./, '')
    } catch {
      continue // URL inválida: se ignora silenciosamente
    }

    const { rows } = await pool.query<{ id: string }>(
      `INSERT INTO fuentes_noticias (url, dominio, estado) VALUES ($1, $2, 'procesando') RETURNING id`,
      [rawUrl, dominio],
    )
    creados.push({ id: rows[0].id, url: rawUrl })
  }

  if (creados.length > 0) {
    runAnalyzeNewsScript(creados)
  }

  res.status(202).json({ fuentes: creados })
})

fuentesRouter.get('/', async (_req, res) => {
  const { rows } = await pool.query(
    `SELECT id, url, dominio, estado, creado_en, procesado_en
     FROM fuentes_noticias ORDER BY creado_en DESC LIMIT 50`,
  )
  res.json(rows)
})
