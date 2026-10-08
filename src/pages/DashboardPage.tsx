import { useState, useMemo } from 'react'
import { useDashboardStats, useTodaysTenders, useTenders } from '../hooks/useTenders'
import { useGemTodayTenders } from '../hooks/useGemTenders'
import { useAllGemTenders } from '../hooks/useAllGemTenders'
import { TrendingUp, FileText, Shield, ArrowRight, FileSearch, Calendar, MapPin, Search, X, RotateCcw } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import { motion } from 'framer-motion'
import { clsx } from 'clsx'
import TenderCard from '../components/tenders/TenderCard'
import GemTenderCard from '../components/tenders/GemTenderCard'
import { COMMON_STATES, extractState } from '../config/filterData'

const lufgaRegularStyle = { fontFamily: "'Lufga', sans-serif", fontWeight: 400 } as const;
const lufgaSemiboldStyle = { fontFamily: "'Lufga', sans-serif", fontWeight: 600 } as const;

const toISODate = (d: Date) => d.toISOString().split('T')[0]
const monthsAgoISO = (months: number) => {
  const d = new Date()
  d.setMonth(d.getMonth() - months)
  return toISODate(d)
}
const formatDate = (iso: string) =>
  iso
    ? new Date(`${iso}T00:00:00`).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' })
    : ''

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

  // Analysis Filters State
  const [portal, setPortal] = useState<'eproc' | 'gem'>('eproc')
  const [dateFrom, setDateFrom] = useState<string>(() => {
    const date = new Date()
    date.setMonth(date.getMonth() - 1)
    return date.toISOString().split('T')[0]
  })
  const [dateTo, setDateTo] = useState<string>(() => {
    return new Date().toISOString().split('T')[0]
  })
  const [selectedState, setSelectedState] = useState<string>('all')
  const [searchKeyword, setSearchKeyword] = useState<string>('')

  // Data for Analysis
  const { data: eprocTenders = [], data: eprocTotalCount } = useTenders({
    date_from: dateFrom || undefined,
    date_to: dateTo || undefined,
    keyword: searchKeyword || undefined,
  })
  const { data: allGemTenders = [] } = useAllGemTenders()

  const filteredTenders = useMemo(() => {
    let list: any[] = []

    if (portal === 'eproc') {
      // Robust flattening for eProcurement data
      if (Array.isArray(eprocTenders)) {
        list = [...eprocTenders]
      } else if (eprocTenders && typeof eprocTenders === 'object') {
        const pages = (eprocTenders as any).pages
        if (Array.isArray(pages)) {
          list = pages.flatMap((page: any) => (Array.isArray(page.tenders) ? page.tenders : []))
        } else {
          // If it's a single page or different structure, try to find tenders array
          list = (eprocTenders as any).tenders || []
        }
      }

      console.log('eProc flattened list length:', list.length);
    } else {
      // GeM data
      list = Array.isArray(allGemTenders) ? [...allGemTenders] : []
      console.log('GeM combined list length:', list.length);
    }

    // 1. Apply Date Filtering (For both, but eProc is handled by hook, GeM needs it here)
    if (dateFrom || dateTo) {
      const from = dateFrom ? new Date(dateFrom) : null
      const to = dateTo ? new Date(dateTo) : null

      list = list.filter(t => {
        if (!t) return false
        const tDate = new Date(t.scraped_at || t.created_at)
        if (from && tDate < from) return false
        if (to && tDate > to) return false
        return true
      })
    }

    // 2. Apply Keyword Filtering
    if (searchKeyword) {
      const kw = searchKeyword.toLowerCase()
      list = list.filter(t =>
        t && (
          t.title?.toLowerCase().includes(kw) ||
          t.organization?.toLowerCase().includes(kw) ||
          t.keywords_matched?.some((k: string) => k.toLowerCase().includes(kw))
        )
      )
    }

    // 3. Apply State Filter (eProc only)
    if (portal === 'eproc' && selectedState !== 'all') {
      list = list.filter(t => {
        if (!t) return false
        // Check both location and source_site as per user feedback
        const location = t.location || t.source_site || ''
        return extractState(location) === selectedState
      })
    }

    console.log('Final filtered list length:', list.length);
    return list
  }, [portal, eprocTenders, allGemTenders, dateFrom, dateTo, selectedState, searchKeyword])

  // Calculate total for display
  const displayTotal = useMemo(() => {
    if (portal === 'eproc') {
      // For eProc, we use the total count from the server if available,
      // but we must account for the client-side State filter since that's not in the hook
      if (selectedState === 'all') {
        // If no state filter, return the server-side total for the date/keyword filters
        return (eprocTotalCount as any)?.pages?.[0]?.total ?? filteredTenders.length
      }
      // If state filter is active, we have to rely on the client-side filtered list
      return filteredTenders.length
    }
    // For GeM, use the filtered list length
    return filteredTenders.length
  }, [portal, eprocTotalCount, filteredTenders, selectedState])

  const totalTodayCount = (todaysEproc?.length ?? 0) + (todaysGem?.length ?? 0)
  const eprocTotal = stats?.eproc_total ?? 0
  const gemTotal = stats?.gem_total ?? 0
  const totalCombined = stats?.total_tenders || 1
  const gemPercentage = Math.round((gemTotal / totalCombined) * 100)
  const eprocPercentage = Math.round((eprocTotal / totalCombined) * 100)

  const handleQuickDate = (months: number) => {
    // Set both ends so the highlighted chip always matches what is applied
    setDateFrom(monthsAgoISO(months))
    setDateTo(toISODate(new Date()))
  }

  const activeMonths = [1, 2, 3].find(m => dateFrom === monthsAgoISO(m) && dateTo === toISODate(new Date()))
  const hasActiveFilters = activeMonths !== 1 || selectedState !== 'all' || searchKeyword !== ''

  const handleResetFilters = () => {
    handleQuickDate(1)
    setSelectedState('all')
    setSearchKeyword('')
  }

  const handleViewAll = () =>
    navigate(portal === 'eproc' ? '/tenders' : '/more-portals', {
      state: {
        portal,
        filters: { date_from: dateFrom, date_to: dateTo, keyword: searchKeyword, state: selectedState },
      },
    })

  const resultContext = [
    portal === 'eproc' ? 'eProcurement' : 'GeM',
    dateFrom && dateTo ? `${formatDate(dateFrom)} to ${formatDate(dateTo)}` : null,
    portal === 'eproc' && selectedState !== 'all' ? selectedState : null,
    searchKeyword ? `"${searchKeyword}"` : null,
  ].filter(Boolean).join(', ')

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

      {/* Tenders Analysis Section */}
      <section className="space-y-4" style={lufgaRegularStyle}>
        <div className="flex items-end justify-between gap-4">
          <div>
            <h2 className="text-lg font-semibold text-slate-800" style={lufgaSemiboldStyle}>Tenders Analysis</h2>
            <p className="text-sm text-slate-500 mt-0.5">
              Filter by portal, dates, state or keyword to see how many tenders match.
            </p>
          </div>
          {hasActiveFilters && (
            <button
              onClick={handleResetFilters}
              className="flex-shrink-0 inline-flex items-center gap-1.5 text-xs font-medium text-slate-500 hover:text-slate-800 hover:bg-slate-100 px-2.5 py-1.5 rounded-lg transition-colors"
            >
              <RotateCcw size={12} /> Reset filters
            </button>
          )}
        </div>

        {/* Filters */}
        <div className="glass-card rounded-xl p-5 space-y-5">
          {/* Keyword search comes first: it's the most-used filter */}
          <div className="relative">
            <Search size={16} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-400 pointer-events-none" />
            <input
              type="text"
              aria-label="Search tenders"
              placeholder="Search by title, organisation or keyword"
              value={searchKeyword}
              onChange={(e) => setSearchKeyword(e.target.value)}
              className="w-full h-11 pl-10 pr-10 rounded-lg border border-slate-200 bg-white text-sm text-slate-800 placeholder:text-slate-400 outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20 transition"
            />
            {searchKeyword && (
              <button
                onClick={() => setSearchKeyword('')}
                aria-label="Clear search"
                className="absolute right-2.5 top-1/2 -translate-y-1/2 p-1 rounded-md text-slate-400 hover:text-slate-700 hover:bg-slate-100 transition-colors"
              >
                <X size={14} />
              </button>
            )}
          </div>

          {/* Fixed 12-col layout so columns never shift when the portal changes.
              Every label row is h-6 so all controls line up on one baseline. */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-12 gap-x-4 gap-y-4 pt-5 border-t border-slate-100">
            {/* Portal */}
            <div className="min-w-0 lg:col-span-3">
              <p className="h-6 text-xs font-medium text-slate-500 flex items-center gap-1.5">
                <Shield size={12} /> Portal
              </p>
              <div role="group" aria-label="Portal" className="grid grid-cols-2 gap-1 p-1 h-9 rounded-lg bg-slate-100">
                {([['eproc', 'eProcurement'], ['gem', 'GeM']] as const).map(([key, label]) => (
                  <button
                    key={key}
                    aria-pressed={portal === key}
                    onClick={() => setPortal(key)}
                    className={clsx(
                      'rounded-md text-xs font-medium transition-all',
                      portal === key
                        ? clsx('bg-white shadow-sm', key === 'eproc' ? 'text-blue-700' : 'text-indigo-700')
                        : 'text-slate-500 hover:text-slate-800'
                    )}
                  >
                    {label}
                  </button>
                ))}
              </div>
            </div>

            {/* Timeline */}
            <div className="min-w-0 md:col-span-2 lg:col-span-6">
              <div className="h-6 flex items-center justify-between gap-2">
                <p className="text-xs font-medium text-slate-500 flex items-center gap-1.5">
                  <Calendar size={12} /> Timeline
                </p>
                <div className="flex items-center gap-1">
                  {[1, 2, 3].map(m => (
                    <button
                      key={m}
                      aria-pressed={activeMonths === m}
                      onClick={() => handleQuickDate(m)}
                      className={clsx(
                        'text-[11px] font-medium px-2 py-0.5 rounded-md transition-colors',
                        activeMonths === m
                          ? 'bg-slate-800 text-white'
                          : 'text-slate-500 hover:bg-slate-100 hover:text-slate-800'
                      )}
                    >
                      {m} {m === 1 ? 'month' : 'months'}
                    </button>
                  ))}
                </div>
              </div>
              <div className="flex items-center gap-2">
                <input
                  type="date"
                  aria-label="From date"
                  value={dateFrom}
                  max={dateTo || undefined}
                  onChange={(e) => setDateFrom(e.target.value)}
                  className="h-9 flex-1 min-w-0 px-3 rounded-lg border border-slate-200 bg-white text-sm text-slate-700 outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20 transition"
                />
                <ArrowRight size={14} className="text-slate-300 flex-shrink-0" />
                <input
                  type="date"
                  aria-label="To date"
                  value={dateTo}
                  min={dateFrom || undefined}
                  onChange={(e) => setDateTo(e.target.value)}
                  className="h-9 flex-1 min-w-0 px-3 rounded-lg border border-slate-200 bg-white text-sm text-slate-700 outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20 transition"
                />
              </div>
            </div>

            {/* State (always rendered so the layout stays stable; disabled for GeM) */}
            <div className="min-w-0 lg:col-span-3">
              <p className="h-6 text-xs font-medium text-slate-500 flex items-center gap-1.5">
                <MapPin size={12} /> State
                {portal !== 'eproc' && <span className="font-normal text-slate-400">eProcurement only</span>}
              </p>
              <select
                aria-label="State"
                value={portal === 'eproc' ? selectedState : 'all'}
                onChange={(e) => setSelectedState(e.target.value)}
                disabled={portal !== 'eproc'}
                className="h-9 w-full px-3 rounded-lg border border-slate-200 bg-white text-sm text-slate-700 outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20 transition disabled:bg-slate-50 disabled:text-slate-400 disabled:cursor-not-allowed"
              >
                <option value="all">All states</option>
                {COMMON_STATES.map(s => <option key={s} value={s}>{s}</option>)}
              </select>
            </div>
          </div>
        </div>

        {/* Results */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <div className="glass-card rounded-xl p-5 sm:col-span-2 flex items-center justify-between gap-4">
            <div className="min-w-0">
              <p className="text-sm font-medium text-slate-500">Tenders found</p>
              <p className="text-4xl font-semibold text-slate-900 mt-1 tabular-nums" style={lufgaSemiboldStyle}>
                {displayTotal}
              </p>
              <p className="text-xs text-slate-500 mt-2 truncate">{resultContext}</p>
            </div>
            <button
              onClick={handleViewAll}
              className={clsx(
                'flex-shrink-0 inline-flex items-center gap-1.5 text-xs font-semibold px-3 py-2 rounded-lg transition-colors',
                portal === 'eproc'
                  ? 'bg-blue-50 text-blue-700 hover:bg-blue-100'
                  : 'bg-indigo-50 text-indigo-700 hover:bg-indigo-100'
              )}
            >
              View these tenders <ArrowRight size={13} />
            </button>
          </div>

          {/* Not built yet: dashed + muted so they read as placeholders, not as zeros */}
          {['Applied', 'Rejected'].map(label => (
            <div key={label} className="rounded-xl border border-dashed border-slate-200 bg-slate-50/60 p-5">
              <p className="text-sm font-medium text-slate-500">{label}</p>
              <p className="text-2xl font-semibold text-slate-300 mt-1">–</p>
              <span className="inline-block mt-2 text-[11px] font-medium text-slate-500 bg-white border border-slate-200 rounded-full px-2 py-0.5">
                Coming soon
              </span>
            </div>
          ))}
        </div>
      </section>

      {totalTodayCount > 0 && (
        <div id="todays-tenders-section" className="scroll-mt-6 space-y-4">
          <h2 className="text-sm font-semibold text-slate-700" style={lufgaSemiboldStyle}>
            Today's Tenders ({totalTodayCount})
          </h2>
          <div className="space-y-3">
            {todaysEproc.map(t => <TenderCard key={t.id} tender={t} />)}
            {todaysGem.map(t => <GemTenderCard key={t.id} tender={t} />)}
          </div>
        </div>
      )}
    </motion.div>
  )
}