// src/components/dashboard/Layout.tsx
import { Outlet, NavLink } from 'react-router-dom'
import { LayoutDashboard, FileSearch, Activity, Play, Loader2, CheckCircle2, AlertCircle, X, ChevronUp, AlertTriangle } from 'lucide-react'
import { usePipeline } from '../../hooks/usePipeline'
import { clsx } from 'clsx'
import { useState, useEffect } from 'react'

const lufgaRegularStyle = { fontFamily: "'Lufga', sans-serif", fontWeight: 400 } as const;
const lufgaSemiboldStyle = { fontFamily: "'Lufga', sans-serif", fontWeight: 600 } as const;

const nav = [
  { to: '/dashboard', icon: LayoutDashboard, label: 'Dashboard' },
  { to: '/tenders',   icon: FileSearch,      label: 'Tenders' },
]

export default function Layout() {
  const { isRunning, loading, error, status, trigger } = usePipeline()
  const [isDisclaimerMinimized, setIsDisclaimerMinimized] = useState(false)
  const [isDisclaimerVisible, setIsDisclaimerVisible] = useState(true)

  const lastSuccess = status?.last_result?.success

  // Load saved preference
  useEffect(() => {
    const dismissed = localStorage.getItem('tenderpulse_disclaimer_dismissed')
    if (dismissed === 'true') {
      setIsDisclaimerVisible(false)
    }
  }, [])

  const handleDismiss = () => {
    setIsDisclaimerVisible(false)
    localStorage.setItem('tenderpulse_disclaimer_dismissed', 'true')
  }

  if (!isDisclaimerVisible) return (
    <div className="flex h-screen overflow-hidden bg-slate-50">
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
              ? <><Loader2 size={13} className="animate-spin" style={lufgaRegularStyle} /> Running...</>
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

        {/* Restore button if dismissed */}
        <div className="p-3 border-t border-slate-100">
          <button
            onClick={() => {
              setIsDisclaimerVisible(true)
              localStorage.removeItem('tenderpulse_disclaimer_dismissed')
            }}
            className="text-xs text-slate-400 hover:text-blue-600 transition-colors w-full text-center"
          >
            Show Disclaimer
          </button>
        </div>
      </aside>

      <main className="flex-1 overflow-y-auto">
        <Outlet />
      </main>
    </div>
  )

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
              ? <><Loader2 size={13} className="animate-spin" style={lufgaRegularStyle} /> Running...</>
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

        {/* Disclaimer Card - Bottom Left Corner */}
        <div className="mt-auto p-3 border-t border-slate-100" style={lufgaRegularStyle}>
          {isDisclaimerMinimized ? (
            // Minimized version
            <button
              onClick={() => setIsDisclaimerMinimized(false)}
              className="w-full flex items-center justify-between gap-2 px-3 py-2 rounded-lg bg-amber-50 hover:bg-amber-100 transition-all group"
            >
              <div className="flex items-center gap-2">
                <AlertTriangle size={14} className="text-amber-600" />
                <span className="text-xs font-medium text-amber-700">Session Notice</span>
              </div>
              <ChevronUp size={12} className="text-amber-500 opacity-0 group-hover:opacity-100 transition-opacity" />
            </button>
          ) : (
            // Expanded card
            <div className="bg-amber-50 rounded-lg border border-amber-200 overflow-hidden shadow-sm">
              {/* Header */}
              <div className="px-3 py-2 bg-amber-100/50 border-b border-amber-200 flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <AlertTriangle size={14} className="text-amber-600" />
                  <span className="text-xs font-semibold text-amber-800" style={lufgaSemiboldStyle}>
                    Session Timeout Notice
                  </span>
                </div>
                <div className="flex items-center gap-1">
                  <button
                    onClick={() => setIsDisclaimerMinimized(true)}
                    className="p-0.5 rounded hover:bg-amber-200 transition-colors"
                    title="Minimize"
                  >
                    <ChevronUp size={12} className="text-amber-600" />
                  </button>
                  <button
                    onClick={handleDismiss}
                    className="p-0.5 rounded hover:bg-amber-200 transition-colors"
                    title="Dismiss"
                  >
                    <X size={12} className="text-amber-600" />
                  </button>
                </div>
              </div>

              {/* Content */}
              <div className="p-3 space-y-2">
                <p className="text-[11px] text-amber-800 leading-relaxed">
                  <span className="font-semibold">⚠️ Open Button URL session may be timed out</span>
                </p>
                
                {/* Steps */}
                <div className="space-y-1.5">
                  <div className="flex items-start gap-1.5 text-[10px]">
                    <span className="inline-flex items-center justify-center w-3.5 h-3.5 rounded-full bg-amber-200 text-amber-800 text-[9px] font-bold">1</span>
                    <span className="text-amber-700">Click <strong className="text-amber-900">[Open]</strong> on any tender</span>
                  </div>
                  
                  <div className="flex items-start gap-1.5 text-[10px]">
                    <span className="inline-flex items-center justify-center w-3.5 h-3.5 rounded-full bg-amber-200 text-amber-800 text-[9px] font-bold">2</span>
                    <span className="text-amber-700">If timeout → Click <strong className="text-amber-900">"Restart Session"</strong> on redirected page</span>
                  </div>
                  
                  <div className="flex items-start gap-1.5 text-[10px]">
                    <span className="inline-flex items-center justify-center w-3.5 h-3.5 rounded-full bg-amber-200 text-amber-800 text-[9px] font-bold">3</span>
                    <span className="text-amber-700">Return here & click <strong className="text-amber-900">[Open]</strong> again</span>
                  </div>
                </div>

                {/* Note */}
                <div className="mt-1.5 pt-1.5 border-t border-amber-200">
                  <p className="text-[9px] text-amber-600 flex items-center gap-1">
                    <span>💡</span>
                    <span>Once per site session of 3-4 minutes  — works after this</span>
                  </p>
                </div>
              </div>
            </div>
          )}
        </div>
      </aside>

      {/* Main content */}
      <main className="flex-1 overflow-y-auto">
        <Outlet />
      </main>
    </div>
  )
}