import { useDashboardStats, useTodaysTenders } from '../hooks/useTenders'
import { formatDistanceToNow, parseISO } from 'date-fns'
import { TrendingUp, Globe, FileText, Clock, Shield, ArrowRight } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import { motion } from 'framer-motion'
import TenderCard from '../components/tenders/TenderCard'

const lufgaRegularStyle = { fontFamily: "'Lufga', sans-serif", fontWeight: 400 } as const;
const lufgaSemiboldStyle = { fontFamily: "'Lufga', sans-serif", fontWeight: 600 } as const;

function StatCard({ label, value, sub, icon: Icon, color }: {
  label: string; value: string | number; sub?: string; icon: any; color: string
}) {
  return (
    <motion.div
      whileHover={{ y: -3 }}
      transition={{ duration: 0.2 }}
      className="glass-card glass-card-hover rounded-xl p-5"
    >
      <div className="flex items-start justify-between">
        <div>
          <p className="text-xs font-medium text-slate-500 uppercase tracking-wide">{label}</p>
          <p className="text-2xl font-semibold text-slate-900 mt-1">{value}</p>
          {sub && <p className="text-xs text-slate-400 mt-0.5">{sub}</p>}
        </div>
        <div className={`w-9 h-9 rounded-lg flex items-center justify-center shadow-sm ${color}`}>
          <Icon size={16} className="text-white" />
        </div>
      </div>
    </motion.div>
  )
}

export default function DashboardPage() {
  const navigate = useNavigate()
  const { data: stats }  = useDashboardStats()
  const { data: todays } = useTodaysTenders()

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3 }}
      className="p-6 max-w-6xl mx-auto space-y-6"
    >
      <div>
        <h1 className="text-xl font-semibold text-slate-900" style={lufgaSemiboldStyle}>Dashboard</h1>
        <p className="text-sm text-slate-500 mt-0.5" style={lufgaRegularStyle}>
          Absstem Tender Monitoring
        </p>
      </div>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4" style={lufgaRegularStyle}>
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
        {/* Quick Actions Card */}
        <motion.div
          whileHover={{ y: -2 }}
          transition={{ duration: 0.2 }}
          className="glass-card rounded-xl p-5"
        >
          <h2 className="text-sm font-semibold text-slate-700 mb-3" style={lufgaSemiboldStyle}>
            Quick Actions
          </h2>
          <div className="space-y-2.5">
            <motion.button
              whileHover={{ scale: 1.01 }}
              whileTap={{ scale: 0.98 }}
              onClick={() => navigate('/more-portals', { state: { portal: 'gem' } })}
              className="w-full flex items-center justify-between px-4 py-2.5 rounded-lg bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-semibold transition-all shadow-sm hover:shadow"
              style={lufgaSemiboldStyle}
            >
              <span className="flex items-center gap-2">
                <Shield size={15} />
                Go to GeM Portal
              </span>
              <ArrowRight size={14} />
            </motion.button>
          </div>
        </motion.div>

        {/* Top keywords */}
        <div className="glass-card rounded-xl p-5">
          <h2 className="text-sm font-semibold text-slate-700 mb-3" style={lufgaSemiboldStyle}>
            Top Keywords
          </h2>
          {!stats?.tenders_by_keyword?.length && <p className="text-sm text-slate-400">No data yet.</p>}
          <div className="space-y-2">
            {stats?.tenders_by_keyword?.slice(0, 6).map(({ keyword, count }: { keyword: string; count: number }) => (
              <div key={keyword} className="flex items-center gap-2">
                <span className="text-xs font-mono bg-slate-100 text-slate-600 px-2 py-0.5 rounded flex-shrink-0">{keyword}</span>
                <div className="flex-1 h-1.5 bg-slate-100 rounded-full overflow-hidden">
                  <div className="h-full bg-blue-500 rounded-full transition-all duration-500" style={{ width: `${Math.min(100, (count / Math.max(stats.total_tenders, 1)) * 500)}%` }} />
                </div>
                <span className="text-xs text-slate-500 flex-shrink-0">{count}</span>
              </div>
            ))}
          </div>
        </div>

        {/* Top sites */}
        <div className="glass-card rounded-xl p-5">
          <h2 className="text-sm font-semibold text-slate-700 mb-3" style={lufgaSemiboldStyle}>
            Top Sources
          </h2>
          {!stats?.tenders_by_site?.length && <p className="text-sm text-slate-400">No data yet.</p>}
          <div className="space-y-2">
            {stats?.tenders_by_site?.slice(0, 6).map(({ site, count }: { site: string; count: number }) => (
              <div key={site} className="flex items-center justify-between py-1">
                <span className="text-xs text-slate-600 truncate" style={lufgaRegularStyle}>
                  {site}
                </span>
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
    </motion.div>
  )
}
