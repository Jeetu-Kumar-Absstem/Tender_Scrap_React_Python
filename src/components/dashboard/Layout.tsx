// src/components/dashboard/Layout.tsx
import { Outlet, NavLink } from 'react-router-dom'
import { LayoutDashboard, FileSearch, Activity, Play, Loader2, CheckCircle2, AlertCircle } from 'lucide-react'
import { usePipeline } from '../../hooks/usePipeline'
import { clsx } from 'clsx'

const nav = [
  { to: '/dashboard', icon: LayoutDashboard, label: 'Dashboard' },
  { to: '/tenders',   icon: FileSearch,      label: 'Tenders' },
]

export default function Layout() {
  const { isRunning, loading, error, status, trigger } = usePipeline()

  const lastSuccess = status?.last_result?.success
  // const lastFinished = status?.last_result?.finished_at

  return (
    <div className="flex h-screen overflow-hidden bg-slate-50">
      {/* Sidebar */}
      <aside className="w-56 flex-shrink-0 bg-white border-r border-slate-200 flex flex-col">

        {/* Logo */}
        <div className="px-5 py-5 border-b border-slate-100">
          <div className="flex items-center gap-2">
            <div className="w-7 h-7 bg-blue-600 rounded-lg flex items-center justify-center">
              <Activity size={14} className="text-white" />
            </div>
            <span className="font-semibold text-slate-900 text-sm">TenderPulse</span>
          </div>
        </div>

        {/* Start Execution button */}
        <div className="px-3 pt-4 pb-2">
          <button
            onClick={trigger}
            disabled={isRunning || loading}
            className={clsx(
              'w-full flex items-center justify-center gap-2 px-3 py-2.5 rounded-lg text-sm font-medium transition-all',
              isRunning || loading
                ? 'bg-blue-100 text-blue-500 cursor-not-allowed'
                : 'bg-blue-600 text-white hover:bg-blue-700 shadow-sm hover:shadow'
            )}
          >
            {isRunning || loading
              ? <><Loader2 size={13} className="animate-spin" /> Running...</>
              : <><Play size={13} /> Start Execution</>
            }
          </button>

          {/* Last run result */}
          {status?.last_result && (
            <div className={clsx(
              'flex items-center gap-1.5 mt-2 px-1 text-[11px]',
              lastSuccess ? 'text-emerald-600' : 'text-red-500'
            )}>
              {lastSuccess
                ? <CheckCircle2 size={10} />
                : <AlertCircle size={10} />
              }
              {lastSuccess ? 'Last run succeeded' : 'Last run failed'}
            </div>
          )}

          {error && (
            <p className="mt-1.5 px-1 text-[11px] text-red-500 leading-tight">
              {error.includes('already running') ? 'Already running' : 'API offline — start server'}
            </p>
          )}
        </div>

        {/* Nav links */}
        <nav className="flex-1 px-3 py-2 space-y-0.5">
          {nav.map(({ to, icon: Icon, label }) => (
            <NavLink
              key={to}
              to={to}
              className={({ isActive }) =>
                `flex items-center gap-2.5 px-3 py-2 rounded-lg text-sm transition-colors ${
                  isActive
                    ? 'bg-blue-50 text-blue-700 font-medium'
                    : 'text-slate-600 hover:bg-slate-50 hover:text-slate-900'
                }`
              }
            >
              <Icon size={15} />
              {label}
            </NavLink>
          ))}
        </nav>

        <div className="px-4 py-3 border-t border-slate-100">
          {/* <p className="text-[11px] text-slate-400">Monitors 40 portals daily</p> */}
        </div>
      </aside>

      {/* Main content */}
      <main className="flex-1 overflow-y-auto">
        <Outlet />
      </main>
    </div>
  )
}
