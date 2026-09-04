import { Router } from 'express'
import { pool } from '../db.js'

export const sugerenciasRouter = Router()

// Cola de Validación IA: sugerencias pendientes de revisión por un analista.
sugerenciasRouter.get('/', async (_req, res) => {
  const { rows } = await pool.query(`
    SELECT s.*, f.url, f.dominio, ti.nombre AS tipo_infraccion_nombre, ti.color_indicador
    FROM incidentes_sugeridos_ia s
    JOIN fuentes_noticias f ON f.id = s.fuente_id
    LEFT JOIN tipos_infraccion ti ON ti.id = s.tipo_infraccion_id
    WHERE s.estado = 'pendiente'
    ORDER BY s.creado_en DESC
  `)
  res.json(rows)
})

sugerenciasRouter.post('/:id/rechazar', async (req, res) => {
  await pool.query(`UPDATE incidentes_sugeridos_ia SET estado = 'rechazado' WHERE id = $1`, [req.params.id])
  res.status(204).end()
})

// Promueve la sugerencia a un incidente real (mismo flujo que "Registrar
// Incidente" desde una alerta de monitoreo). Si la IA no determinó un tipo
// de infracción, el analista debe indicarlo en el body.
sugerenciasRouter.post('/:id/aprobar', async (req, res) => {
  const { id } = req.params
  const tipoInfraccionIdOverride: string | undefined = req.body?.tipo_infraccion_id

  const { rows } = await pool.query(
    `SELECT s.*, ti.gravedad_sugerida
     FROM incidentes_sugeridos_ia s
     LEFT JOIN tipos_infraccion ti ON ti.id = s.tipo_infraccion_id
     WHERE s.id = $1 AND s.estado = 'pendiente'`,
    [id],
  )
  const sugerencia = rows[0]
  if (!sugerencia) {
    res.status(404).json({ error: 'Sugerencia no encontrada o ya procesada' })
    return
  }

  const tipoInfraccionId = tipoInfraccionIdOverride ?? sugerencia.tipo_infraccion_id
  if (!tipoInfraccionId) {
    res.status(400).json({ error: 'Debe indicarse tipo_infraccion_id: la IA no pudo determinarlo' })
    return
  }

  const { rows: incidenteRows } = await pool.query(
    `INSERT INTO incidentes (tipo_infraccion_id, descripcion, gravedad, estado, fecha_deteccion)
     VALUES ($1, $2, $3, 'sospechoso', now())
     RETURNING id, codigo`,
    [tipoInfraccionId, sugerencia.resumen ?? sugerencia.titular, sugerencia.gravedad_sugerida ?? 'medio'],
  )
  const incidente = incidenteRows[0]

  await pool.query(`UPDATE incidentes_sugeridos_ia SET estado = 'aprobado', incidente_id = $1 WHERE id = $2`, [
    incidente.id,
    id,
  ])

  res.json({ incidente })
})
