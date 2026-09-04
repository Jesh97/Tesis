import type { InputHTMLAttributes, ReactNode } from 'react'

interface TextFieldProps extends InputHTMLAttributes<HTMLInputElement> {
  label: string
  icon: ReactNode
  trailingAction?: ReactNode
}

export function TextField({
  label,
  icon,
  trailingAction,
  id,
  className = '',
  ...props
}: TextFieldProps) {
  return (
    <div className="flex flex-col gap-2">
      <label
        htmlFor={id}
        className="text-xs font-semibold tracking-wide text-slate-500 uppercase"
      >
        {label}
      </label>
      <div className="flex items-center gap-2 rounded-lg border border-slate-300 bg-slate-50 px-3 py-2.5 focus-within:border-slate-400 focus-within:ring-1 focus-within:ring-slate-400">
        <span className="shrink-0 text-slate-400">{icon}</span>
        <input
          id={id}
          className={`w-full bg-transparent text-sm text-slate-800 placeholder:text-slate-400 focus:outline-none ${className}`}
          {...props}
        />
        {trailingAction ? <span className="shrink-0">{trailingAction}</span> : null}
      </div>
    </div>
  )
}
