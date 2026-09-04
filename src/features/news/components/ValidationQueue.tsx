import { InboxIcon } from '../../../components/icons'
import { processingItems, validationItems } from '../data/mockValidationItems'
import { ProcessingRow } from './ProcessingRow'
import { ValidationCard } from './ValidationCard'

export function ValidationQueue() {
  const pendingCount = validationItems.length + processingItems.length

  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2 text-sm font-semibold text-slate-900">
          <InboxIcon className="h-4 w-4" />
          Cola de Validación IA
        </div>
        <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-medium text-slate-600">
          {pendingCount} Pendientes
        </span>
      </div>

      {validationItems.map((item) => (
        <ValidationCard key={item.id} item={item} />
      ))}

      {processingItems.map((item) => (
        <ProcessingRow key={item.id} item={item} />
      ))}
    </div>
  )
}
