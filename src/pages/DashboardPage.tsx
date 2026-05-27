import { useDashboardStats, useScrapeRuns, useTodaysTenders } from '../hooks/useTenders'
import { formatDistanceToNow, parseISO } from 'date-fns'
import { CheckCircle, XCircle, Clock, TrendingUp, Globe, FileText, Mail } from 'lucide-react'
import type { RunStatus } from '../types/tender'
import TenderCard from '../components/tenders/TenderCard'

function StatCard({ label, value, sub, icon: Icon, color }: {
  label: string; value: string | number; sub?: string; icon: any; color: string
}) {
  return (
    <div className="bg-white rounded-xl border border-slate-200 p-5">
      <div className="flex items-start justify-between">
        <div>
          <p className="text-xs font-medium text-slate-500 uppercase tracking-wide">{label}</p>
          <p className="text-2xl font-semibold text-slate-900 mt-1">{value}</p>
          {sub && <p className="text-xs text-slate-400 mt-0.5">{sub}</p>}
        </div>
        <div className={`w-9 h-9 rounded-lg flex items-center justify-center ${color}`}>
          <Icon size={16} className="text-white" />
        </div>
      </div>
    </div>
  )
}

const runStatusBadge: Record<RunStatus, { label: string; cls: string; icon: any }> = {
  running:   { label: 'Running',   cls: 'bg-yellow-50 text-yellow-700 border-yellow-200', icon: Clock },
  completed: { label: 'Completed', cls: 'bg-green-50  text-green-700  border-green-200',  icon: CheckCircle },
  failed:    { label: 'Failed',    cls: 'bg-red-50    text-red-700    border-red-200',    icon: XCircle },
}

export default function DashboardPage() {
  const { data: stats }  = useDashboardStats()
  const { data: runs }   = useScrapeRuns(5)
  const { data: todays } = useTodaysTenders()

  return (
    <div className="p-6 max-w-6xl mx-auto space-y-6">
      <div>
        <h1 className="text-xl font-semibold text-slate-900">Dashboard</h1>
        <p className="text-sm text-slate-500 mt-0.5">Government tender monitoring · updated daily</p>
      </div>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard label="Total Tenders"     value={stats?.total_tenders ?? '—'} icon={FileText}   color="bg-blue-500" />
        <StatCard label="New Today"         value={stats?.new_today ?? '—'}      icon={TrendingUp} color="bg-emerald-500" />
        <StatCard label="Portals Monitored" value={stats?.sites_monitored ?? '—'} icon={Globe}     color="bg-violet-500" />
        <StatCard
          label="Last Run"
          value={stats?.last_run_status ?? '—'}
          sub={stats?.last_run_at ? formatDistanceToNow(parseISO(stats.last_run_at), { addSuffix: true }) : undefined}
          icon={Clock}
          color={stats?.last_run_status === 'completed' ? 'bg-slate-500' : 'bg-orange-500'}
        />
      </div>

      <div className="grid lg:grid-cols-3 gap-6">
        {/* Recent runs */}
        <div className="bg-white rounded-xl border border-slate-200 p-5">
          <h2 className="text-sm font-semibold text-slate-700 mb-3">Recent Runs</h2>
          {!runs?.length && <p className="text-sm text-slate-400">No runs yet.</p>}
          <div className="space-y-2">
            {runs?.map(run => {
              const badge = runStatusBadge[run.status] ?? runStatusBadge.completed
              const Icon  = badge.icon
              return (
                <div key={run.id} className="flex items-center justify-between py-2 border-b border-slate-50 last:border-0">
                  <div>
                    <div className={`inline-flex items-center gap-1 text-xs px-2 py-0.5 rounded border ${badge.cls}`}>
                      <Icon size={10} />{badge.label}
                    </div>
                    <p className="text-xs text-slate-400 mt-0.5">
                      {formatDistanceToNow(parseISO(run.started_at), { addSuffix: true })}
                    </p>
                  </div>
                  <div className="text-right">
                    <p className="text-sm font-medium text-slate-900">{run.new_count} new</p>
                    <div className="flex items-center gap-1 justify-end">
                      {run.email_sent && <Mail size={10} className="text-blue-400" />}
                      <p className="text-xs text-slate-400">{run.sites_ok}/{run.sites_total} ok</p>
                    </div>
                  </div>
                </div>
              )
            })}
          </div>
        </div>

        {/* Top keywords */}
        <div className="bg-white rounded-xl border border-slate-200 p-5">
          <h2 className="text-sm font-semibold text-slate-700 mb-3">Top Keywords</h2>
          {!stats?.tenders_by_keyword?.length && <p className="text-sm text-slate-400">No data yet.</p>}
          <div className="space-y-2">
            {stats?.tenders_by_keyword?.slice(0, 6).map(({ keyword, count }: { keyword: string; count: number }) => (
              <div key={keyword} className="flex items-center gap-2">
                <span className="text-xs font-mono bg-slate-100 text-slate-600 px-2 py-0.5 rounded flex-shrink-0">{keyword}</span>
                <div className="flex-1 h-1.5 bg-slate-100 rounded-full overflow-hidden">
                  <div className="h-full bg-blue-500 rounded-full" style={{ width: `${Math.min(100, (count / Math.max(stats.total_tenders, 1)) * 500)}%` }} />
                </div>
                <span className="text-xs text-slate-500 flex-shrink-0">{count}</span>
              </div>
            ))}
          </div>
        </div>

        {/* Top sites */}
        <div className="bg-white rounded-xl border border-slate-200 p-5">
          <h2 className="text-sm font-semibold text-slate-700 mb-3">Top Sources</h2>
          {!stats?.tenders_by_site?.length && <p className="text-sm text-slate-400">No data yet.</p>}
          <div className="space-y-2">
            {stats?.tenders_by_site?.slice(0, 6).map(({ site, count }: { site: string; count: number }) => (
              <div key={site} className="flex items-center justify-between py-1">
                <span className="text-xs text-slate-600 truncate">{site}</span>
                <span className="text-xs font-medium text-slate-900 ml-2">{count}</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {(todays?.length ?? 0) > 0 && (
        <div>
          <h2 className="text-sm font-semibold text-slate-700 mb-3">Today's Tenders ({todays!.length})</h2>
          <div className="space-y-3">
            {todays!.map(t => <TenderCard key={t.id} tender={t} />)}
          </div>
        </div>
      )}
    </div>
  )
}
