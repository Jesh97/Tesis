import { ShieldCheckIcon, BellIcon, SettingsIcon, SearchIcon } from '../icons'

interface TopBarProps {
  title: string
  searchPlaceholder?: string
}

export function TopBar({ title, searchPlaceholder }: TopBarProps) {
  return (
    <header className="flex h-14 shrink-0 items-center justify-between gap-6 border-b border-slate-800 bg-slate-900 px-5 text-white">
      <div className="flex shrink-0 items-center gap-2 text-sm font-semibold tracking-wide uppercase">
        <ShieldCheckIcon className="h-5 w-5 text-red-500" />
        {title}
      </div>

      {searchPlaceholder ? (
        <div className="flex max-w-md flex-1 items-center gap-2 rounded-lg bg-slate-800 px-3 py-2">
          <SearchIcon className="h-4 w-4 shrink-0 text-slate-400" />
          <input
            type="text"
            placeholder={searchPlaceholder}
            className="w-full bg-transparent text-sm text-white placeholder:text-slate-400 focus:outline-none"
          />
        </div>
      ) : (
        <div className="flex-1" />
      )}

      <div className="flex shrink-0 items-center gap-4">
        <button className="text-slate-300 hover:text-white" aria-label="Notificaciones">
          <BellIcon className="h-5 w-5" />
        </button>
        <button className="text-slate-300 hover:text-white" aria-label="Configuración">
          <SettingsIcon className="h-5 w-5" />
        </button>
        <div className="h-8 w-8 overflow-hidden rounded-full bg-slate-700">
          <div className="flex h-full w-full items-center justify-center text-xs font-semibold text-slate-300">
            U
          </div>
        </div>
      </div>
    </header>
  )
}
