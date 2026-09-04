import type { InputHTMLAttributes } from 'react'

interface CheckboxProps extends InputHTMLAttributes<HTMLInputElement> {
  label: string
}

export function Checkbox({ label, id, className = '', ...props }: CheckboxProps) {
  return (
    <label htmlFor={id} className="flex cursor-pointer items-center gap-2 text-sm text-slate-600">
      <input
        id={id}
        type="checkbox"
        className={`h-4 w-4 rounded border-slate-300 text-red-700 focus:ring-red-700 ${className}`}
        {...props}
      />
      {label}
    </label>
  )
}
