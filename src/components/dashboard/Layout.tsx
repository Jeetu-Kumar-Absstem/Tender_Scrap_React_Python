// src/components/dashboard/Layout.tsx
import { Outlet, NavLink } from 'react-router-dom'
import { LayoutDashboard, FileSearch, Activity, Play, Loader2, CheckCircle2, AlertCircle, X, ChevronUp, AlertTriangle, Square, Terminal, ChevronDown, Trash2, LogOut, Hospital } from 'lucide-react'
import { usePipeline } from '../../hooks/usePipeline'
import { useLogs } from '../../hooks/useLogs'
import { supabase } from '../../lib/supabase'
import { clsx } from 'clsx'
import { useState, useEffect, useRef } from 'react'

const lufgaRegularStyle  = { fontFamily: "'Lufga', sans-serif", fontWeight: 400 } as const
const lufgaSemiboldStyle = { fontFamily: "'Lufga', sans-serif", fontWeight: 600 } as const

const nav = [
  { to: '/dashboard', icon: LayoutDashboard, label: 'Dashboard' },
  { to: '/tenders',   icon: FileSearch,      label: 'Tenders' },
  { to: '/hospitals', icon: Hospital,        label: 'Hospital Data' },
]

// ─── Terminal log panel ───────────────────────────────────────
function LogPanel({ onClose }: { onClose: () => void }) {
  const { logs, clear } = useLogs(true)
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [logs])

  const lineColor = (type: 'out' | 'err' | 'sys') => {
    if (type === 'err') return 'text-red-400'
    if (type === 'sys') return 'text-blue-400'
    return 'text-emerald-300'
  }

  const formatTs = (iso: string) =>
    new Date(iso).toLocaleTimeString('en-US', { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' })

  return (
    <div className="flex flex-col border-t border-slate-700" style={{ height: 280 }}>
      <div className="flex items-center justify-between px-3 py-1.5 bg-slate-800 border-b border-slate-700 flex-shrink-0">
        <div className="flex items-center gap-2">
          <Terminal size={11} className="text-emerald-400" />
          <span className="text-[10px] font-mono text-slate-300 tracking-wide">PIPELINE LOGS</span>
          {logs.length > 0 && (
            <span className="text-[9px] text-slate-500 font-mono">{logs.length} lines</span>
          )}
        </div>
        <div className="flex items-center gap-1">
          <button onClick={clear} title="Clear logs" className="p-1 rounded hover:bg-slate-700 transition-colors">
            <Trash2 size={10} className="text-slate-400 hover:text-slate-200" />
          </button>
          <button onClick={onClose} title="Hide logs" className="p-1 rounded hover:bg-slate-700 transition-colors">
            <ChevronDown size={10} className="text-slate-400 hover:text-slate-200" />
          </button>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto bg-slate-900 px-2 py-1.5 font-mono">
        {logs.length === 0 ? (
          <p className="text-[10px] text-slate-600 italic px-1 pt-1">Waiting for pipeline output...</p>
        ) : (
          logs.map((line, i) => (
            <div key={i} className="flex gap-2 leading-relaxed">
              <span className="text-[9px] text-slate-600 flex-shrink-0 pt-px">{formatTs(line.ts)}</span>
              <span className={clsx('text-[10px] break-all whitespace-pre-wrap', lineColor(line.type))}>{line.text}</span>
            </div>
          ))
        )}
        <div ref={bottomRef} />
      </div>
    </div>
  )
}

// ─── Sidebar inner content ────────────────────────────────────
function SidebarContent({
  isRunning, loading, error, status, trigger, stop,
  isDisclaimerMinimized, setIsDisclaimerMinimized,
  isDisclaimerVisible, handleDismiss,
  showDisclaimer,
  logsOpen, setLogsOpen,
}: any) {
  const lastSuccess = status?.last_result?.success
  const runStatus   = status?.last_result?.status

  const getStatusDisplay = () => {
    if (runStatus === 'interrupted') return { label: 'Last run interrupted', icon: 'alert', color: 'text-amber-600' }
    return {
      label: lastSuccess ? 'Last run succeeded' : 'Last run failed',
      icon:  lastSuccess ? 'check' : 'alert',
      color: lastSuccess ? 'text-emerald-600' : 'text-red-500',
    }
  }
  const statusDisplay = getStatusDisplay()

  return (
    <>
      {/* Logo */}
      <div className="px-5 py-5 border-b border-slate-100">
        <div className="flex items-center gap-2">
          <div className="w-7 h-7 bg-blue-600 rounded-lg flex items-center justify-center">
            <Activity size={14} className="text-white" />
          </div>
          <span className="font-semibold text-slate-900 text-sm">Absstem TenderHub</span>
        </div>
      </div>

      {/* Start Execution button */}
      <div className="px-3 pt-4 pb-2">
        <button
          onClick={trigger}
          disabled={isRunning || loading}
          title="Execution may take time"
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

        {isRunning && (
          <button
            onClick={stop}
            className="mt-2 w-full flex items-center justify-center gap-2 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm font-medium text-red-600 hover:bg-red-100 transition-colors"
          >
            <Square size={13} fill="currentColor" className="text-red-600" />
            Stop Execution
          </button>
        )}

        {status?.last_result && (
          <div className={clsx('flex items-center gap-1.5 mt-2 px-1 text-[11px]', statusDisplay.color)}>
            {statusDisplay.icon === 'check' && <CheckCircle2 size={10} />}
            {statusDisplay.icon === 'alert' && runStatus === 'interrupted' && <AlertTriangle size={10} />}
            {statusDisplay.icon === 'alert' && runStatus !== 'interrupted' && <AlertCircle size={10} />}
            {statusDisplay.label}
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

      {/* Bottom section */}
      <div className="mt-auto">
        {isDisclaimerVisible && (
          <div className="p-3 border-t border-slate-100" style={lufgaRegularStyle}>
            {isDisclaimerMinimized ? (
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
              <div className="bg-amber-50 rounded-lg border border-amber-200 overflow-hidden shadow-sm">
                <div className="px-3 py-2 bg-amber-100/50 border-b border-amber-200 flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <AlertTriangle size={14} className="text-amber-600" />
                    <span className="text-xs font-semibold text-amber-800" style={lufgaSemiboldStyle}>
                      Session Timeout Notice
                    </span>
                  </div>
                  <div className="flex items-center gap-1">
                    <button onClick={() => setIsDisclaimerMinimized(true)} className="p-0.5 rounded hover:bg-amber-200 transition-colors" title="Minimize">
                      <ChevronUp size={12} className="text-amber-600" />
                    </button>
                    <button onClick={handleDismiss} className="p-0.5 rounded hover:bg-amber-200 transition-colors" title="Dismiss">
                      <X size={12} className="text-amber-600" />
                    </button>
                  </div>
                </div>
                <div className="p-3 space-y-2">
                  <p className="text-[11px] text-amber-800 leading-relaxed">
                    <span className="font-semibold">⚠️ Open Button URL session may be timed out</span>
                  </p>
                  <div className="space-y-1.5">
                    {[
                      ['Click', '[Open]', 'on any tender'],
                      ['If timeout → Click', '"Restart Session"', 'on redirected page'],
                      ['Return here & click', '[Open]', 'again'],
                    ].map(([pre, bold, post], i) => (
                      <div key={i} className="flex items-start gap-1.5 text-[10px]">
                        <span className="inline-flex items-center justify-center w-3.5 h-3.5 rounded-full bg-amber-200 text-amber-800 text-[9px] font-bold flex-shrink-0">{i + 1}</span>
                        <span className="text-amber-700">{pre} <strong className="text-amber-900">{bold}</strong> {post}</span>
                      </div>
                    ))}
                  </div>
                  <div className="mt-1.5 pt-1.5 border-t border-amber-200">
                    <p className="text-[9px] text-amber-600 flex items-center gap-1">
                      <span>💡</span>
                      <span>Once per site session of 3-4 minutes — works after this</span>
                    </p>
                  </div>
                </div>
              </div>
            )}
          </div>
        )}

        {!isDisclaimerVisible && (
          <div className="px-3 pt-2 border-t border-slate-100">
            <button
              onClick={showDisclaimer}
              className="text-xs text-slate-400 hover:text-blue-600 transition-colors w-full text-center py-1"
            >
              Show Disclaimer
            </button>
          </div>
        )}

        {/* Logs toggle button */}
        <div className="px-3 py-2 border-t border-slate-100">
          <button
            onClick={() => setLogsOpen((v: boolean) => !v)}
            className={clsx(
              'w-full flex items-center justify-between gap-2 px-3 py-2 rounded-lg text-xs font-medium transition-all',
              logsOpen
                ? 'bg-slate-800 text-emerald-400'
                : 'bg-slate-100 text-slate-600 hover:bg-slate-200 hover:text-slate-900'
            )}
          >
            <div className="flex items-center gap-2">
              <Terminal size={12} />
              <span>Logs</span>
              {isRunning && <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />}
            </div>
            {logsOpen ? <ChevronDown size={11} /> : <ChevronUp size={11} />}
          </button>
        </div>
      </div>
    </>
  )
}

// ─── Main Layout ──────────────────────────────────────────────
export default function Layout() {
  const { isRunning, loading, error, status, trigger, stop } = usePipeline()
  const [isDisclaimerMinimized, setIsDisclaimerMinimized] = useState(false)
  const [isDisclaimerVisible,   setIsDisclaimerVisible]   = useState(true)
  const [logsOpen, setLogsOpen] = useState(false)

  useEffect(() => {
    const dismissed = localStorage.getItem('tenderpulse_disclaimer_dismissed')
    if (dismissed === 'true') setIsDisclaimerVisible(false)
  }, [])

  const handleDismiss = () => {
    setIsDisclaimerVisible(false)
    localStorage.setItem('tenderpulse_disclaimer_dismissed', 'true')
  }

  const showDisclaimer = () => {
    setIsDisclaimerVisible(true)
    localStorage.removeItem('tenderpulse_disclaimer_dismissed')
  }

  const handleSignOut = async () => {
    await supabase.auth.signOut()
  }

  const sharedProps = {
    isRunning, loading, error, status, trigger, stop,
    isDisclaimerMinimized, setIsDisclaimerMinimized,
    isDisclaimerVisible, handleDismiss, showDisclaimer,
    logsOpen, setLogsOpen,
  }

  return (
    <div className="flex h-screen overflow-hidden bg-slate-50">
      {/* Sidebar */}
      <aside className={clsx(
        'flex-shrink-0 bg-white border-r border-slate-200 flex flex-col transition-all duration-300',
        logsOpen ? 'w-80' : 'w-56'
      )}>
        <div className="flex flex-col flex-1 overflow-hidden">
          <div className="flex flex-col flex-1 overflow-y-auto">
            <SidebarContent {...sharedProps} />
          </div>
          {logsOpen && <LogPanel onClose={() => setLogsOpen(false)} />}
        </div>
      </aside>

      {/* Main content */}
      <div className="flex-1 flex flex-col overflow-hidden">
        {/* Top bar with Sign Out */}
        <div className="flex-shrink-0 h-10 bg-white border-b border-slate-200 flex items-center justify-end px-4">
          <button
            onClick={handleSignOut}
            className="flex items-center gap-1.5 text-xs text-slate-500 hover:text-red-500 transition-colors px-2 py-1 rounded hover:bg-red-50"
          >
            <LogOut size={12} />
            Sign Out
          </button>
        </div>
        <main className="flex-1 overflow-y-auto">
          <Outlet />
        </main>
      </div>
    </div>
  )
}