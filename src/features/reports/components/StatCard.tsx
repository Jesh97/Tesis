import type { ReactNode } from 'react'
import { TrendingUpIcon } from '../../../components/icons'

interface StatCardProps {
  label: string
  value: string
  trend?: string
  icon: ReactNode
  iconClassName: string
}

export function StatCard({ label, value, trend, icon, iconClassName }: StatCardProps) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4">
      <div className="flex items-center justify-between">
        <p className="text-[11px] font-semibold tracking-wide text-slate-400 uppercase">{label}</p>
        <span className={`flex h-8 w-8 items-center justify-center rounded-full ${iconClassName}`}>{icon}</span>
      </div>
      <div className="mt-2 flex items-baseline gap-2">
        <p className="text-2xl font-bold text-slate-900">{value}</p>
        {trend ? (
          <span className="flex items-center gap-0.5 text-xs font-semibold text-emerald-600">
            <TrendingUpIcon className="h-3.5 w-3.5" />
            {trend}
          </span>
        ) : null}
      </div>
    </div>
  )
}
