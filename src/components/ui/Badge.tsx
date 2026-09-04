import type { ReactNode } from 'react'

type BadgeVariant = 'red' | 'amber' | 'gray' | 'green'

const variantClasses: Record<BadgeVariant, string> = {
  red: 'bg-red-100 text-red-700',
  amber: 'bg-amber-100 text-amber-700',
  gray: 'bg-slate-100 text-slate-600',
  green: 'bg-emerald-100 text-emerald-700',
}

interface BadgeProps {
  variant: BadgeVariant
  children: ReactNode
}

export function Badge({ variant, children }: BadgeProps) {
  return (
    <span
      className={`inline-flex items-center rounded px-2 py-0.5 text-[11px] font-bold tracking-wide uppercase ${variantClasses[variant]}`}
    >
      {children}
    </span>
  )
}
