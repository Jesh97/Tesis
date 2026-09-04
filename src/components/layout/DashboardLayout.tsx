import type { ReactNode } from 'react'
import { Sidebar } from './Sidebar'
import { TopBar } from './TopBar'

interface DashboardLayoutProps {
  title: string
  searchPlaceholder?: string
  children: ReactNode
}

export function DashboardLayout({ title, searchPlaceholder, children }: DashboardLayoutProps) {
  return (
    <div className="flex h-svh flex-col overflow-hidden bg-slate-100">
      <TopBar title={title} searchPlaceholder={searchPlaceholder} />
      <div className="flex min-h-0 flex-1">
        <Sidebar />
        <main className="relative flex-1 overflow-hidden">{children}</main>
      </div>
    </div>
  )
}
