import { useState } from 'react'
import { CircleDotIcon, PlayIcon, SparklesIcon } from '../../../components/icons'

const urlLimit = 10

interface WebAnalyzerCardProps {
  onAnalizar: (urls: string[]) => Promise<void>
}

export function WebAnalyzerCard({ onAnalizar }: WebAnalyzerCardProps) {
  const [urls, setUrls] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [enviando, setEnviando] = useState(false)

  const listaUrls = urls
    .split('\n')
    .map((linea) => linea.trim())
    .filter((linea) => linea.length > 0)
  const urlCount = listaUrls.length

  async function handleIniciar() {
    setError(null)
    if (listaUrls.length === 0) {
      setError('Ingrese al menos una URL')
      return
    }
    if (listaUrls.length > urlLimit) {
      setError(`Máximo ${urlLimit} URLs por lote`)
      return
    }

    setEnviando(true)
    try {
      await onAnalizar(listaUrls)
      setUrls('')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error desconocido')
    } finally {
      setEnviando(false)
    }
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="rounded-xl border border-slate-200 bg-white p-5">
        <div className="flex items-center gap-2">
          <span className="flex h-9 w-9 items-center justify-center rounded-full bg-slate-900 text-white">
            <SparklesIcon className="h-4 w-4" />
          </span>
          <h2 className="text-sm font-semibold text-slate-900">Analizador Web</h2>
        </div>

        <p className="mt-3 text-xs leading-relaxed text-slate-500">
          Ingrese uno o múltiples enlaces HTTP/HTTPS. Cada enlace debe ir en una nueva línea.
        </p>

        <label htmlFor="source-urls" className="mt-4 block text-[11px] font-semibold tracking-wide text-slate-500 uppercase">
          URLs de fuentes
        </label>
        <textarea
          id="source-urls"
          rows={5}
          value={urls}
          onChange={(event) => setUrls(event.target.value)}
          placeholder={'https://ejemplo.com/noticia-pesca-1\nhttps://ejemplo.com/reporte-incautacion'}
          className="mt-2 w-full resize-none rounded-lg border border-slate-300 bg-slate-50 p-3 text-xs text-slate-700 placeholder:text-slate-400 focus:border-slate-400 focus:outline-none focus:ring-1 focus:ring-slate-400"
        />

        <div className="mt-2 flex items-center justify-between text-[11px] text-slate-400">
          <span>Límite lote: {urlLimit} URLs</span>
          <span>
            {urlCount}/{urlLimit}
          </span>
        </div>

        {error && <p className="mt-2 text-xs text-red-600">{error}</p>}

        <button
          type="button"
          onClick={() => void handleIniciar()}
          disabled={enviando}
          className="mt-4 flex w-full items-center justify-center gap-2 rounded-lg bg-slate-900 px-4 py-3 text-sm font-semibold text-white hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-50"
        >
          <PlayIcon className="h-4 w-4" />
          {enviando ? 'Enviando…' : 'Iniciar Análisis'}
        </button>
      </div>

      <div className="flex items-center justify-between rounded-xl border border-slate-200 bg-white px-4 py-3">
        <div className="flex items-center gap-2 text-xs font-semibold tracking-wide text-slate-600 uppercase">
          <CircleDotIcon className="h-4 w-4 text-emerald-500" />
          Motor NLP Activo
        </div>
        <span className="rounded bg-slate-100 px-2 py-0.5 text-[11px] font-medium text-slate-500">v2.4.1</span>
      </div>
    </div>
  )
}
