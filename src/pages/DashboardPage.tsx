import { useDashboardStats, useTodaysTenders } from '../hooks/useTenders'
import { useGemTodayTenders } from '../hooks/useGemTenders'
import { TrendingUp, FileText, Shield, ArrowRight, FileSearch, PieChart } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import { motion } from 'framer-motion'
import TenderCard from '../components/tenders/TenderCard'
import GemTenderCard from '../components/tenders/GemTenderCard'

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
          {sub && <p className="text-xs text-slate-500 font-medium mt-1">{sub}</p>}
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
  const { data: todaysEproc = [] } = useTodaysTenders()
  const { data: todaysGem = [] } = useGemTodayTenders()

  const totalTodayCount = (todaysEproc?.length ?? 0) + (todaysGem?.length ?? 0)
  const eprocTotal = stats?.eproc_total ?? 0
  const gemTotal = stats?.gem_total ?? 0
  const totalCombined = stats?.total_tenders || 1
  const gemPercentage = Math.round((gemTotal / totalCombined) * 100)
  const eprocPercentage = Math.round((eprocTotal / totalCombined) * 100)

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
          Absstem Tender Monitoring & Platform Analytics
        </p>
      </div>

      {/* Top 4 Stat Cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4" style={lufgaRegularStyle}>
        <StatCard label="Total Tenders" value={stats?.total_tenders ?? '—'} sub={`${stats?.sites_monitored ?? 0} portals monitored`} icon={FileText} color="bg-blue-500" />
        <StatCard label="eProcurement Tenders" value={eprocTotal} sub={`${eprocPercentage}% of total database`} icon={FileSearch} color="bg-blue-600" />
        <StatCard label="GeM.gov Tenders" value={gemTotal} sub={`${gemPercentage}% of total database`} icon={Shield} color="bg-indigo-600" />
        <StatCard label="New Today" value={stats?.new_today ?? '—'} sub={`${stats?.eproc_today ?? 0} eProc | ${stats?.gem_today ?? 0} GeM`} icon={TrendingUp} color="bg-emerald-500" />
      </div>

      <div className="grid lg:grid-cols-3 gap-6">
        {/* Quick Actions Card */}
        <motion.div
          whileHover={{ y: -2 }}
          transition={{ duration: 0.2 }}
          className="glass-card rounded-xl p-5 flex flex-col justify-between"
        >
          <div>
            <h2 className="text-sm font-semibold text-slate-700 mb-3" style={lufgaSemiboldStyle}>
              Quick Actions
            </h2>
            <div className="space-y-2">
              <motion.button
                whileHover={{ scale: 1.01 }}
                whileTap={{ scale: 0.98 }}
                onClick={() => navigate('/tenders')}
                className="w-full flex items-center justify-between px-3.5 py-2.5 rounded-lg bg-blue-600 hover:bg-blue-700 text-white text-xs font-semibold transition-all shadow-sm"
                style={lufgaSemiboldStyle}
              >
                <span className="flex items-center gap-2">
                  <FileSearch size={15} />
                  Go to eProcurement ({eprocTotal})
                </span>
                <ArrowRight size={14} />
              </motion.button>

              <motion.button
                whileHover={{ scale: 1.01 }}
                whileTap={{ scale: 0.98 }}
                onClick={() => navigate('/more-portals', { state: { portal: 'gem' } })}
                className="w-full flex items-center justify-between px-3.5 py-2.5 rounded-lg bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-semibold transition-all shadow-sm"
                style={lufgaSemiboldStyle}
              >
                <span className="flex items-center gap-2">
                  <Shield size={15} />
                  Go to GeM Portal ({gemTotal})
                </span>
                <ArrowRight size={14} />
              </motion.button>

              <motion.button
                whileHover={{ scale: 1.01 }}
                whileTap={{ scale: 0.98 }}
                onClick={() => {
                  const el = document.getElementById('todays-tenders-section')
                  if (el) el.scrollIntoView({ behavior: 'smooth' })
                }}
                className="w-full flex items-center justify-between px-3.5 py-2.5 rounded-lg bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-semibold transition-all shadow-sm"
                style={lufgaSemiboldStyle}
              >
                <span className="flex items-center gap-2">
                  <TrendingUp size={15} />
                  Today's Tenders ({totalTodayCount})
                </span>
                <ArrowRight size={14} />
              </motion.button>
            </div>
          </div>
        </motion.div>

        {/* Independent eProcurement Keywords */}
        <div className="glass-card rounded-xl p-5">
          <div className="flex items-center gap-2 mb-3">
            <FileSearch size={15} className="text-blue-600" />
            <h2 className="text-sm font-semibold text-slate-700" style={lufgaSemiboldStyle}>
              eProcurement Keywords
            </h2>
          </div>
          {!stats?.tenders_by_keyword?.length && <p className="text-sm text-slate-400">No data yet.</p>}
          <div className="space-y-2">
            {stats?.tenders_by_keyword?.slice(0, 5).map(({ keyword, count }: { keyword: string; count: number }) => (
              <div key={keyword} className="flex items-center gap-2">
                <span className="text-xs bg-blue-50 text-blue-700 border border-blue-100 px-2 py-0.5 rounded flex-shrink-0 truncate max-w-[140px]">{keyword}</span>
                <div className="flex-1 h-1.5 bg-slate-100 rounded-full overflow-hidden">
                  <div className="h-full bg-blue-600 rounded-full transition-all duration-500" style={{ width: `${Math.min(100, (count / Math.max(eprocTotal, 1)) * 300)}%` }} />
                </div>
                <span className="text-xs text-slate-500 flex-shrink-0 font-medium">{count}</span>
              </div>
            ))}
          </div>
        </div>

        {/* Independent GeM Keywords */}
        <div className="glass-card rounded-xl p-5">
          <div className="flex items-center gap-2 mb-3">
            <Shield size={15} className="text-indigo-600" />
            <h2 className="text-sm font-semibold text-slate-700" style={lufgaSemiboldStyle}>
              GeM.gov Keywords
            </h2>
          </div>
          {!stats?.gem_keywords?.length && <p className="text-sm text-slate-400">No data yet.</p>}
          <div className="space-y-2">
            {stats?.gem_keywords?.slice(0, 5).map(({ keyword, count }: { keyword: string; count: number }) => (
              <div key={keyword} className="flex items-center gap-2">
                <span className="text-xs bg-indigo-50 text-indigo-700 border border-indigo-100 px-2 py-0.5 rounded flex-shrink-0 truncate max-w-[140px]">{keyword}</span>
                <div className="flex-1 h-1.5 bg-slate-100 rounded-full overflow-hidden">
                  <div className="h-full bg-indigo-600 rounded-full transition-all duration-500" style={{ width: `${Math.min(100, (count / Math.max(gemTotal, 1)) * 300)}%` }} />
                </div>
                <span className="text-xs text-slate-500 flex-shrink-0 font-medium">{count}</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Independent Platform Volume Breakdown */}
      <div className="glass-card rounded-xl p-5 space-y-4">
        <div className="flex items-center gap-2">
          <PieChart size={16} className="text-slate-700" />
          <h2 className="text-sm font-semibold text-slate-800" style={lufgaSemiboldStyle}>
            Platform Volume Distribution
          </h2>
        </div>
        <div className="grid md:grid-cols-2 gap-4">
          <div className="space-y-1.5 p-3 rounded-lg bg-blue-50/50 border border-blue-100">
            <div className="flex justify-between text-xs font-semibold text-blue-900">
              <span className="flex items-center gap-1.5">
                <FileSearch size={14} className="text-blue-600" />
                eProcurement Tenders
              </span>
              <span>{eprocTotal} ({eprocPercentage}%)</span>
            </div>
            <div className="h-2 w-full bg-blue-100 rounded-full overflow-hidden">
              <div className="h-full bg-blue-600 rounded-full transition-all duration-500" style={{ width: `${eprocPercentage}%` }} />
            </div>
          </div>

          <div className="space-y-1.5 p-3 rounded-lg bg-indigo-50/50 border border-indigo-100">
            <div className="flex justify-between text-xs font-semibold text-indigo-900">
              <span className="flex items-center gap-1.5">
                <Shield size={14} className="text-indigo-600" />
                GeM.gov Tenders
              </span>
              <span>{gemTotal} ({gemPercentage}%)</span>
            </div>
            <div className="h-2 w-full bg-indigo-100 rounded-full overflow-hidden">
              <div className="h-full bg-indigo-600 rounded-full transition-all duration-500" style={{ width: `${gemPercentage}%` }} />
            </div>
          </div>
        </div>
      </div>

      {totalTodayCount > 0 && (
        <div id="todays-tenders-section" className="scroll-mt-6">
          <h2 className="text-sm font-semibold text-slate-700 mb-3">Today's Tenders ({totalTodayCount})</h2>
          <div className="space-y-3">
            {todaysEproc.map(t => <TenderCard key={t.id} tender={t} />)}
            {todaysGem.map(t => <GemTenderCard key={t.id} tender={t} />)}
          </div>
        </div>
      )}
    </motion.div>
  )
}
