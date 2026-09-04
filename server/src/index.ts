import 'dotenv/config'
import cors from 'cors'
import express from 'express'
import { embarcacionesRouter } from './routes/embarcaciones.js'
import { fuentesRouter } from './routes/fuentes.js'
import { sugerenciasRouter } from './routes/sugerencias.js'

const app = express()
app.use(cors())
app.use(express.json())

app.get('/health', (_req, res) => res.json({ ok: true }))
app.use('/api/fuentes', fuentesRouter)
app.use('/api/sugerencias', sugerenciasRouter)
app.use('/api/embarcaciones', embarcacionesRouter)

const port = process.env.PORT ? Number(process.env.PORT) : 8787
app.listen(port, () => {
  console.log(`Servidor escuchando en http://localhost:${port}`)
})
