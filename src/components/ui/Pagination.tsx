import { ChevronLeftIcon, ChevronRightIcon } from '../icons'

interface PaginationProps {
  page: number
  pageCount: number
  totalItems: number
  pageSize: number
  onPageChange: (page: number) => void
}

function getPageItems(page: number, pageCount: number): (number | 'ellipsis')[] {
  if (pageCount <= 5) {
    return Array.from({ length: pageCount }, (_, i) => i + 1)
  }
  if (page <= 3) {
    return [1, 2, 3, 'ellipsis', pageCount]
  }
  if (page >= pageCount - 2) {
    return [1, 'ellipsis', pageCount - 2, pageCount - 1, pageCount]
  }
  return [1, 'ellipsis', page, 'ellipsis', pageCount]
}

export function Pagination({ page, pageCount, totalItems, pageSize, onPageChange }: PaginationProps) {
  const start = (page - 1) * pageSize + 1
  const end = Math.min(page * pageSize, totalItems)
  const items = getPageItems(page, pageCount)

  return (
    <div className="flex items-center justify-between px-4 py-3 text-sm text-slate-500">
      <p>
        Mostrando {start} a {end} de {totalItems} incidentes
      </p>

      <div className="flex items-center gap-1">
        <button
          aria-label="Página anterior"
          disabled={page === 1}
          onClick={() => onPageChange(page - 1)}
          className="flex h-8 w-8 items-center justify-center rounded-lg text-slate-500 hover:bg-slate-100 disabled:cursor-not-allowed disabled:opacity-40"
        >
          <ChevronLeftIcon className="h-4 w-4" />
        </button>

        {items.map((item, index) =>
          item === 'ellipsis' ? (
            <span key={`ellipsis-${index}`} className="px-2">
              …
            </span>
          ) : (
            <button
              key={item}
              onClick={() => onPageChange(item)}
              className={`flex h-8 w-8 items-center justify-center rounded-lg text-sm font-medium ${
                item === page ? 'bg-slate-900 text-white' : 'text-slate-600 hover:bg-slate-100'
              }`}
            >
              {item}
            </button>
          ),
        )}

        <button
          aria-label="Página siguiente"
          disabled={page === pageCount}
          onClick={() => onPageChange(page + 1)}
          className="flex h-8 w-8 items-center justify-center rounded-lg text-slate-500 hover:bg-slate-100 disabled:cursor-not-allowed disabled:opacity-40"
        >
          <ChevronRightIcon className="h-4 w-4" />
        </button>
      </div>
    </div>
  )
}
