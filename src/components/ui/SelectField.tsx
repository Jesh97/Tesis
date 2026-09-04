import type { ReactNode, SelectHTMLAttributes } from 'react'
import { ChevronDownIcon } from '../icons'

interface SelectFieldProps extends SelectHTMLAttributes<HTMLSelectElement> {
  label: string
  icon?: ReactNode
  children: ReactNode
}

export function SelectField({ label, icon, id, className = '', children, ...props }: SelectFieldProps) {
  return (
    <div className="flex flex-col gap-2">
      <label htmlFor={id} className="text-xs font-semibold tracking-wide text-slate-500 uppercase">
        {label}
      </label>
      <div className="flex items-center gap-2 rounded-lg border border-slate-300 bg-slate-50 px-3 py-2.5 focus-within:border-slate-400 focus-within:ring-1 focus-within:ring-slate-400">
        {icon ? <span className="shrink-0 text-slate-400">{icon}</span> : null}
        <select
          id={id}
          className={`w-full appearance-none bg-transparent text-sm text-slate-800 focus:outline-none ${className}`}
          {...props}
        >
          {children}
        </select>
        <ChevronDownIcon className="h-4 w-4 shrink-0 text-slate-400" />
      </div>
    </div>
  )
}
