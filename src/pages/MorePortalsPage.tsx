// src/pages/MorePortalsPage.tsx
import { useState, useMemo } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Play, Square, Loader2, CheckCircle2, AlertCircle, Globe,
  Clock, FileText, TrendingUp, Search, X, Filter, MapPin,
  RefreshCw, Archive, RotateCcw, Calendar, ChevronDown, ChevronUp,
} from 'lucide-react'
import { clsx } from 'clsx'
import { format, parseISO } from 'date-fns'
import { useTypeD } from '../hooks/useTypeD'
import { useTypeC } from '../hooks/useTypeC'
import { useTender18Tenders, type Tender18Tender } from '../hooks/useTender18'
import { useGemTenders, type GemTender } from '../hooks/useGemTenders'
import Tender18Card from '../components/tenders/Tender18Card'
import GemTenderCard from '../components/tenders/GemTenderCard'
import PortalTabs from '../components/portals/PortalTabs'
import ComingSoonCard from '../components/portals/ComingSoonCard'
import { PORTALS, getPortalById, type PortalConfig } from '../config/portals'
import {
  COMMON_KEYWORDS,
  extractState,
  getUniqueStates,
} from '../config/filterData'

const lufgaRegularStyle = { fontFamily: "'Lufga', sans-serif", fontWeight: 400 } as const
const lufgaSemiboldStyle = { fontFamily: "'Lufga', sans-serif", fontWeight: 600 } as const

export default function MorePortalsPage() {
  const navigate = useNavigate()

  // Portal selection
  const [activePortalId, setActivePortalId] = useState<string>('tender18')

  // Get current portal config
  const currentPortal: PortalConfig = getPortalById(activePortalId) || PORTALS[0]
  const isComingSoon: boolean = currentPortal?.comingSoon || false

  // Portal-specific hooks
  const typeD = useTypeD()
  const typeC = useTypeC()
  const { data: tender18Tenders = [], refetch: refetchTender18, isLoading: isLoadingTender18 } = useTender18Tenders()
  const { data: gemTenders = [], refetch: refetchGem, isLoading: isLoadingGem } = useGemTenders()

  // Determine which hook to use based on active portal
  const isTender18 = activePortalId === 'tender18'

  const { isRunning, loading, error, status, trigger, stop } = isTender18 ? typeD : typeC
  const tenders = isTender18 ? tender18Tenders : gemTenders
  const refetch = isTender18 ? refetchTender18 : refetchGem
  const isLoading = isTender18 ? isLoadingTender18 : isLoadingGem

  // Toggle for showing/hiding filters
  const [showFilters, setShowFilters] = useState<boolean>(false)

  // Global filters (applied across all portals)
  const [selectedKeyword, setSelectedKeyword] = useState<string>('all')
  const [selectedState, setSelectedState] = useState<string>('all')
  const [searchQuery, setSearchQuery] = useState<string>('')
  
  // Date range filters
  const [dateFrom, setDateFrom] = useState<string>('')
  const [dateTo, setDateTo] = useState<string>('')

  // Get all keywords from filterData (always show all keywords)
  const allKeywords: string[] = useMemo(() => {
    return COMMON_KEYWORDS.sort()
  }, [])

  // Get unique states from tenders (only show states that exist)
  const allStates: string[] = useMemo(() => {
    return getUniqueStates(tenders)
  }, [tenders])

  // Filter tenders using global filters + date range
  const filteredTenders = useMemo(() => {
    if (isComingSoon) return []

    return tenders.filter((t: any) => {
      // Keyword filter
      if (selectedKeyword !== 'all' && !(t.keywords_matched || []).includes(selectedKeyword)) {
        return false
      }

      // State filter
      if (selectedState !== 'all') {
        const state = extractState(t.location)
        if (state !== selectedState) return false
      }

      // Search query
      if (searchQuery) {
        const searchLower = searchQuery.toLowerCase()
        const match =
          (t.title?.toLowerCase().includes(searchLower) || false) ||
          (t.reference_number?.toLowerCase().includes(searchLower) || false) ||
          (t.organization?.toLowerCase().includes(searchLower) || false) ||
          (t.location?.toLowerCase().includes(searchLower) || false)
        if (!match) return false
      }

      // Date range filter
      if (t.deadline) {
        try {
          const deadlineDate = parseISO(t.deadline)
          
          // Filter: date from
          if (dateFrom) {
            const fromDate = parseISO(dateFrom)
            if (deadlineDate < fromDate) return false
          }
          
          // Filter: date to
          if (dateTo) {
            const toDate = parseISO(dateTo)
            // Set to end of day for inclusive filtering
            toDate.setHours(23, 59, 59, 999)
            if (deadlineDate > toDate) return false
          }
        } catch (e) {
          // If date parsing fails, skip this filter
        }
      } else {
        // If no deadline, exclude from date filter if dateFrom or dateTo is set
        if (dateFrom || dateTo) return false
      }

      return true
    })
  }, [tenders, selectedKeyword, selectedState, searchQuery, dateFrom, dateTo, isComingSoon])

  const lastResult = status?.last_result

  // Count active filters
  const activeFilterCount = useMemo(() => {
    let count = 0
    if (selectedKeyword !== 'all') count++
    if (selectedState !== 'all') count++
    if (searchQuery) count++
    if (dateFrom) count++
    if (dateTo) count++
    return count
  }, [selectedKeyword, selectedState, searchQuery, dateFrom, dateTo])

  const handleRunScraper = async (): Promise<void> => {
    if (isComingSoon) return
    console.log(`[MorePortalsPage] Running ${currentPortal.name} scraper...`)
    await trigger()
    setTimeout(() => {
      refetch()
    }, 3000)
  }

  const handleRefresh = (): void => {
    if (isComingSoon) return
    refetch()
  }

  const handlePortalChange = (portalId: string): void => {
    setActivePortalId(portalId)
    // Don't reset filters when changing portals - they are global
  }

  const handleClearFilters = (): void => {
    setSelectedKeyword('all')
    setSelectedState('all')
    setSearchQuery('')
    setDateFrom('')
    setDateTo('')
  }

  const toggleFilters = (): void => {
    setShowFilters(!showFilters)
  }

  // If coming soon, show the coming soon card
  if (isComingSoon) {
    return (
      <div className="p-6 max-w-6xl mx-auto space-y-6">
        <div className="flex items-center justify-between">
          <h1 className="text-xl font-semibold text-slate-900" style={lufgaSemiboldStyle}>
            More Portals
          </h1>
          <ArchiveButton onClick={() => navigate('/archive')} />
        </div>

        <PortalTabs activePortal={activePortalId} onPortalChange={handlePortalChange} />

        <ComingSoonCard portal={currentPortal} />
      </div>
    )
  }

  return (
    <div className="p-6 max-w-6xl mx-auto space-y-6">
      {/* Page header */}
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold text-slate-900" style={lufgaSemiboldStyle}>
          More Portals
        </h1>
        <ArchiveButton onClick={() => navigate('/archive')} />
      </div>

      {/* Portal Tabs */}
      <PortalTabs activePortal={activePortalId} onPortalChange={handlePortalChange} />

      {/* Scraper Control Card */}
      <div className="bg-white rounded-xl border border-slate-200 p-6">
        <div className="flex items-start justify-between">
          <div>
            <div className="flex items-center gap-2">
              <currentPortal.icon size={18} className={`text-${currentPortal.color}-600`} />
              <h2 className="text-sm font-semibold text-slate-900" style={lufgaSemiboldStyle}>
                {currentPortal.name} Scraper
              </h2>
              <span className="text-xs bg-green-100 text-green-700 px-2 py-0.5 rounded-full">
                {tenders.length} in DB
              </span>
            </div>
            <p className="text-xs text-slate-500 mt-1" style={lufgaRegularStyle}>
              {currentPortal.description} - Stored in separate table
            </p>
            <div className="flex items-center gap-4 mt-3 flex-wrap">
              <div className="flex items-center gap-1.5 text-xs text-slate-500">
                <Clock size={12} />
                <span>Status: {isRunning ? 'Running...' : 'Idle'}</span>
              </div>
              {lastResult && (
                <div
                  className={clsx(
                    'flex items-center gap-1.5 text-xs',
                    lastResult.success ? 'text-emerald-600' : 'text-red-500'
                  )}
                >
                  {lastResult.success ? <CheckCircle2 size={12} /> : <AlertCircle size={12} />}
                  <span>{lastResult.success ? 'Last run succeeded' : 'Last run failed'}</span>
                  {lastResult.finished_at && (
                    <span className="text-slate-400">
                      {new Date(lastResult.finished_at).toLocaleTimeString()}
                    </span>
                  )}
                </div>
              )}
              {error && (
                <div className="flex items-center gap-1.5 text-xs text-red-500">
                  <AlertCircle size={12} />
                  <span className="max-w-xs truncate">{error}</span>
                </div>
              )}
            </div>
          </div>
          <div className="flex items-center gap-2 flex-shrink-0">
            <button
              onClick={handleRefresh}
              disabled={isLoading}
              className="flex items-center gap-1 px-3 py-2 rounded-lg border bg-cyan-500 border-black-200 text-black-600 hover:bg-green-500 transition-colors text-sm"
              title="Refresh data"
            >
              <RefreshCw size={14} className={clsx(isLoading && 'animate-spin')} />
              Refresh
            </button>
            {isRunning ? (
              <button
                onClick={stop}
                className="flex items-center gap-2 px-4 py-2 rounded-lg border border-red-200 bg-red-50 text-red-600 hover:bg-red-100 transition-colors text-sm font-medium"
              >
                <Square size={14} fill="currentColor" />
                Stop
              </button>
            ) : (
              <button
                onClick={handleRunScraper}
                disabled={loading}
                className={clsx(
                  'flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all',
                  loading
                    ? 'bg-blue-100 text-blue-500 cursor-not-allowed'
                    : 'bg-blue-600 text-white hover:bg-blue-700 shadow-sm hover:shadow'
                )}
              >
                {loading ? (
                  <>
                    <Loader2 size={14} className="animate-spin" /> Starting...
                  </>
                ) : (
                  <>
                    <Play size={14} /> Run Scraper
                  </>
                )}
              </button>
            )}
          </div>
        </div>

        {/* Quick stats */}
        <div className="mt-4 pt-4 border-t border-slate-100 grid grid-cols-4 gap-4">
          <div className="flex items-center gap-2">
            <FileText size={14} className="text-blue-500" />
            <div>
              <p className="text-[10px] text-slate-400 uppercase tracking-wide">Total Found</p>
              <p className="text-sm font-semibold text-slate-900">{tenders.length}</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <TrendingUp size={14} className="text-emerald-500" />
            <div>
              <p className="text-[10px] text-slate-400 uppercase tracking-wide">Keywords</p>
              <p className="text-sm font-semibold text-slate-900">{allKeywords.length}</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <Globe size={14} className="text-violet-500" />
            <div>
              <p className="text-[10px] text-slate-400 uppercase tracking-wide">Source</p>
              <p className="text-sm font-semibold text-slate-900">{currentPortal.name}</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <Filter size={14} className="text-amber-500" />
            <div>
              <p className="text-[10px] text-slate-400 uppercase tracking-wide">Showing</p>
              <p className="text-sm font-semibold text-slate-900">{filteredTenders.length}</p>
            </div>
          </div>
        </div>
      </div>

      {/* Filters Toggle Button & Active Filters Indicator */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <button
            onClick={toggleFilters}
            className={clsx(
              'flex items-center gap-2 px-4 py-2 rounded-lg border transition-all text-sm font-medium',
              showFilters
                ? 'bg-green-500 border-black-200 text-black-700'
                : 'bg-cyan-500 border-black-200 text-black-600 hover:bg-green-500'
            )}
            style={lufgaRegularStyle}
          >
            <Filter size={14} />
            Filters
            {showFilters ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
            {activeFilterCount > 0 && (
              <span className="ml-1 bg-blue-500 text-white text-[10px] font-bold px-1.5 py-0.5 rounded-full min-w-[18px] text-center">
                {activeFilterCount}
              </span>
            )}
          </button>
          
          {activeFilterCount > 0 && (
            <button
              onClick={handleClearFilters}
              className="flex items-center gap-1 px-3 py-1.5 rounded-lg border border-slate-200 text-slate-500 hover:bg-slate-50 transition-colors text-xs"
              style={lufgaRegularStyle}
            >
              <RotateCcw size={12} />
              Clear All Filters
            </button>
          )}
        </div>

        <span className="text-xs text-slate-400" style={lufgaRegularStyle}>
          {isLoading ? 'Loading...' : `${filteredTenders.length} results`}
        </span>
      </div>

      {/* Filters Panel - Conditionally Rendered */}
      {showFilters && (
        <div className="bg-white rounded-xl border border-slate-200 p-4 space-y-3 animate-in slide-in-from-top-2 duration-200">
          <div className="flex flex-wrap items-center gap-3">
            {/* Keyword Filter */}
            <div className="flex items-center gap-1.5">
              <span className="text-xs text-black-500 font-medium" style={lufgaRegularStyle}>
                Keyword:
              </span>
              <select
                value={selectedKeyword}
                onChange={(e) => setSelectedKeyword(e.target.value)}
                className="text-xs border border-slate-200 rounded-lg px-2 py-1 focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white min-w-[180px] max-h-[200px] overflow-y-auto"
                style={lufgaRegularStyle}
              >
                <option value="all">All Keywords</option>
                {allKeywords.map((kw: string) => (
                  <option key={kw} value={kw}>
                    {kw}
                  </option>
                ))}
              </select>
            </div>

            {/* State Filter */}
            <div className="flex items-center gap-1.5">
              <MapPin size={12} className="text-slate-400" />
              <span className="text-xs text-slate-400">State:</span>
              <select
                value={selectedState}
                onChange={(e) => setSelectedState(e.target.value)}
                className="text-xs border border-slate-200 rounded-lg px-2 py-1 focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white"
                style={lufgaRegularStyle}
              >
                <option value="all">All States</option>
                {allStates.map((state: string) => (
                  <option key={state} value={state}>
                    {state}
                  </option>
                ))}
              </select>
            </div>

            {/* Date Range Filters */}
            <div className="flex items-center gap-1.5">
              <Calendar size={12} className="text-slate-400" />
              <span className="text-xs text-slate-400">Date:</span>
              <input
                type="date"
                value={dateFrom}
                onChange={(e) => setDateFrom(e.target.value)}
                className="text-xs border border-slate-200 rounded-lg px-2 py-1 focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white w-[140px]"
                style={lufgaRegularStyle}
                title="Date From"
              />
              <span className="text-xs text-slate-400">→</span>
              <input
                type="date"
                value={dateTo}
                onChange={(e) => setDateTo(e.target.value)}
                className="text-xs border border-slate-200 rounded-lg px-2 py-1 focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white w-[140px]"
                style={lufgaRegularStyle}
                title="Date To"
              />
            </div>

            {/* Search Input */}
            <div className="relative flex-1 min-w-[200px]">
              <Search size={14} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-slate-400" />
              <input
                type="text"
                placeholder="Search tenders..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full pl-8 pr-8 py-1.5 border border-slate-200 rounded-lg text-xs focus:outline-none focus:ring-2 focus:ring-blue-500"
                style={lufgaRegularStyle}
              />
              {searchQuery && (
                <button
                  onClick={() => setSearchQuery('')}
                  className="absolute right-2 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600"
                >
                  <X size={12} />
                </button>
              )}
            </div>

            {/* Clear Filters Button inside panel */}
            {activeFilterCount > 0 && (
              <button
                onClick={handleClearFilters}
                className="flex items-center gap-1 px-3 py-1.5 rounded-lg border border-slate-200 text-slate-600 hover:bg-slate-50 transition-colors text-xs"
                style={lufgaRegularStyle}
              >
                <RotateCcw size={12} />
                Clear Filters
              </button>
            )}
          </div>

          {/* Active Filters Display */}
          {activeFilterCount > 0 && (
            <div className="flex items-center gap-2 pt-2 border-t border-slate-100 flex-wrap">
              <span className="text-[10px] text-slate-400 uppercase tracking-wide">
                Active Filters:
              </span>
              {selectedKeyword !== 'all' && (
                <span className="text-[10px] bg-blue-50 text-blue-600 px-2 py-0.5 rounded border border-blue-200">
                  Keyword: {selectedKeyword}
                </span>
              )}
              {selectedState !== 'all' && (
                <span className="text-[10px] bg-blue-50 text-blue-600 px-2 py-0.5 rounded border border-blue-200">
                  State: {selectedState}
                </span>
              )}
              {dateFrom && (
                <span className="text-[10px] bg-blue-50 text-blue-600 px-2 py-0.5 rounded border border-blue-200">
                  From: {format(parseISO(dateFrom), 'dd MMM yyyy')}
                </span>
              )}
              {dateTo && (
                <span className="text-[10px] bg-blue-50 text-blue-600 px-2 py-0.5 rounded border border-blue-200">
                  To: {format(parseISO(dateTo), 'dd MMM yyyy')}
                </span>
              )}
              {searchQuery && (
                <span className="text-[10px] bg-blue-50 text-blue-600 px-2 py-0.5 rounded border border-blue-200">
                  Search: "{searchQuery}"
                </span>
              )}
            </div>
          )}
        </div>
      )}

      {/* Tenders */}
      <div>
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-sm font-semibold text-slate-900" style={lufgaSemiboldStyle}>
            {currentPortal.name} Results ({filteredTenders.length})
          </h2>
        </div>
        {isLoading ? (
          <div className="bg-white rounded-xl border border-slate-200 p-8 text-center">
            <Loader2 size={32} className="text-blue-500 animate-spin mx-auto mb-3" />
            <p className="text-sm text-slate-500" style={lufgaRegularStyle}>
              Loading tenders...
            </p>
          </div>
        ) : filteredTenders.length === 0 ? (
          <div className="bg-white rounded-xl border border-slate-200 p-8 text-center">
            <Globe size={32} className="text-slate-300 mx-auto mb-3" />
            <p className="text-sm text-slate-500" style={lufgaRegularStyle}>
              {tenders.length === 0
                ? `No tenders scraped from ${currentPortal.name} yet.`
                : 'No tenders match your filters.'}
            </p>
            <p className="text-xs text-slate-400 mt-1">
              {tenders.length === 0
                ? 'Click "Run Scraper" above to start scraping.'
                : 'Try adjusting your filters.'}
            </p>
          </div>
        ) : (
          <div className="space-y-3">
            {filteredTenders.map((tender: any) => (
              isTender18 ? (
                <Tender18Card key={tender.id} tender={tender as Tender18Tender} />
              ) : (
                <GemTenderCard key={tender.id} tender={tender as GemTender} />
              )
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

// ─── Archive button component ─────────────────────────────────────────────────

function ArchiveButton({ onClick }: { onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      className="flex items-center gap-2 px-3 py-2 rounded-lg border border-black-400 text-black-700 hover:bg-green-500 hover:border-black-600 transition-colors text-sm bg-cyan-500"
    >
      <Archive size={14} className="text-slate-500" />
      Archive Tenders
    </button>
  )
}