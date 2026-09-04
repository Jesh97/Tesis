import type { ReactNode } from 'react'
import { NavLink } from 'react-router-dom'
import {
  AlertTriangleIcon,
  AnchorIcon,
  FileTextIcon,
  HelpCircleIcon,
  LayoutGridIcon,
  LogOutIcon,
  RssIcon,
} from '../icons'

interface NavItem {
  label: string
  to: string
  icon: ReactNode
}

const navItems: NavItem[] = [
  { label: 'Monitoreo', to: '/monitoreo', icon: <LayoutGridIcon className="h-4 w-4" /> },
  { label: 'Incidentes', to: '/incidentes', icon: <AlertTriangleIcon className="h-4 w-4" /> },
  { label: 'Noticias', to: '/noticias', icon: <RssIcon className="h-4 w-4" /> },
  { label: 'Reportes', to: '/reportes', icon: <FileTextIcon className="h-4 w-4" /> },
]

export function Sidebar() {
  return (
    <aside className="flex h-full w-64 shrink-0 flex-col border-r border-slate-200 bg-white">
      <div className="flex items-center gap-2 border-b border-slate-200 px-5 py-4">
        <AnchorIcon className="h-5 w-5 text-red-700" />
        <div className="leading-tight">
          <p className="text-xs font-semibold tracking-wide text-red-700 uppercase">
            Ministerio de Producción
          </p>
          <p className="text-xs text-slate-500">Dirección de Supervisión</p>
        </div>
      </div>

      <nav className="flex flex-col gap-1 p-3">
        {navItems.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            className={({ isActive }) =>
              `flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium tracking-wide uppercase transition-colors ${
                isActive
                  ? 'bg-slate-900 text-white'
                  : 'text-slate-600 hover:bg-slate-100'
              }`
            }
          >
            {item.icon}
            {item.label}
          </NavLink>
        ))}
      </nav>

      <div className="mt-auto flex flex-col gap-3 p-3">
        <button className="flex w-full items-center justify-center gap-2 rounded-lg bg-red-700 px-4 py-3 text-sm font-semibold tracking-wide text-white uppercase transition-colors hover:bg-red-800">
          <AlertTriangleIcon className="h-4 w-4" />
          Reportar incidencia
        </button>

        <div className="flex flex-col gap-1 border-t border-slate-200 pt-3">
          <button className="flex items-center gap-2 rounded-lg px-3 py-2 text-sm text-slate-500 hover:bg-slate-100">
            <HelpCircleIcon className="h-4 w-4" />
            Ayuda
          </button>
          <button className="flex items-center gap-2 rounded-lg px-3 py-2 text-sm text-slate-500 hover:bg-slate-100">
            <LogOutIcon className="h-4 w-4" />
            Cerrar Sesión
          </button>
        </div>
      </div>
    </aside>
  )
}
