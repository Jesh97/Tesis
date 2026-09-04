import { LoaderIcon } from '../../../components/icons'
import type { ProcessingItem } from '../data/mockValidationItems'

export function ProcessingRow({ item }: { item: ProcessingItem }) {
  return (
    <div className="flex items-center gap-3 rounded-xl border border-slate-200 bg-white p-4">
      <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-slate-100 text-slate-400">
        <LoaderIcon className="h-4 w-4 animate-spin" />
      </span>
      <div className="min-w-0 flex-1">
        <p className="truncate text-sm font-medium text-slate-700">Procesando: {item.source}</p>
        <p className="text-[11px] tracking-wide text-slate-400 uppercase">{item.stage}</p>
      </div>
      <span className="shrink-0 rounded bg-slate-100 px-2 py-1 text-[10px] font-bold tracking-wide text-slate-500 uppercase">
        En Proceso
      </span>
    </div>
  )
}
