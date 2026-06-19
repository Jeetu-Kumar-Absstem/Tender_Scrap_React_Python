// src/pages/MorePortalsPage.tsx
import { useState, useMemo } from 'react'
import { Play, Square, Loader2, CheckCircle2, AlertCircle, Globe, Clock, FileText, TrendingUp, Search, X, Filter, MapPin, RefreshCw } from 'lucide-react'
import { clsx } from 'clsx'
import { useTypeD } from '../hooks/useTypeD'
import { useTender18Tenders, type Tender18Tender } from '../hooks/useTender18'
import Tender18Card from '../components/tenders/Tender18Card'
import PortalTabs from '../components/portals/PortalTabs'
import ComingSoonCard from '../components/portals/ComingSoonCard'
import { PORTALS, getPortalById, type PortalConfig } from '../config/portals'

const lufgaRegularStyle = { fontFamily: "'Lufga', sans-serif", fontWeight: 400 } as const
const lufgaSemiboldStyle = { fontFamily: "'Lufga', sans-serif", fontWeight: 600 } as const

// Extract state from location
function extractState(location: string | null): string {
  if (!location) return 'Unknown'
  
  const states: string[] = [
    'Andaman', 'Andhra', 'Arunachal', 'Assam', 'Bihar', 'Chandigarh', 
    'Chhattisgarh', 'Dadra', 'Daman', 'Delhi', 'Goa', 'Gujarat', 
    'Haryana', 'Himachal', 'Jammu', 'Jharkhand', 'Karnataka', 'Kerala', 
    'Ladakh', 'Lakshadweep', 'Madhya', 'Maharashtra', 'Manipur', 'Meghalaya', 
    'Mizoram', 'Nagaland', 'Odisha', 'Puducherry', 'Punjab', 'Rajasthan', 
    'Sikkim', 'Tamil', 'Telangana', 'Tripura', 'Uttar', 'Uttarakhand', 
    'West Bengal'
  ]
  
  for (const state of states) {
    if (location.toLowerCase().includes(state.toLowerCase())) {
      return state
    }
  }
  
  return 'Other'
}

export default function MorePortalsPage() {
  // Portal selection
  const [activePortalId, setActivePortalId] = useState<string>('tender18')
  
  // Get current portal config
  const currentPortal: PortalConfig = getPortalById(activePortalId) || PORTALS[0]
  const isComingSoon: boolean = currentPortal?.comingSoon || false
  
  // Tender18 hooks
  const { isRunning, loading, error, status, trigger, stop } = useTypeD()
  const { data: tenders = [], refetch, isLoading } = useTender18Tenders()
  
  // Filters
  const [keywordFilter, setKeywordFilter] = useState<string>('')
  const [selectedKeyword, setSelectedKeyword] = useState<string>('all')
  const [selectedState, setSelectedState] = useState<string>('all')

  // Get unique keywords from all tenders
  const allKeywords: string[] = useMemo(() => {
    return Array.from(
      new Set(tenders.flatMap((t: Tender18Tender) => t.keywords_matched || []))
    ).sort()
  }, [tenders])

  // Get unique states from all tenders
  const allStates: string[] = useMemo(() => {
    const stateSet = new Set<string>()
    tenders.forEach((t: Tender18Tender) => {
      const state = extractState(t.location)
      stateSet.add(state)
    })
    return Array.from(stateSet).sort()
  }, [tenders])

  // Filter tenders
  const filteredTenders: Tender18Tender[] = useMemo(() => {
    if (isComingSoon) return []
    
    return tenders.filter((t: Tender18Tender) => {
      // Keyword filter
      if (selectedKeyword !== 'all' && !(t.keywords_matched || []).includes(selectedKeyword)) {
        return false
      }
      
      // State filter
      if (selectedState !== 'all') {
        const state = extractState(t.location)
        if (state !== selectedState) return false
      }
      
      // Search filter
      if (keywordFilter) {
        const searchLower = keywordFilter.toLowerCase()
        const match = (
          (t.title?.toLowerCase().includes(searchLower) || false) ||
          (t.reference_number?.toLowerCase().includes(searchLower) || false) ||
          (t.organization?.toLowerCase().includes(searchLower) || false) ||
          (t.location?.toLowerCase().includes(searchLower) || false)
        )
        if (!match) return false
      }
      
      return true
    })
  }, [tenders, selectedKeyword, selectedState, keywordFilter, isComingSoon])

  const lastResult = status?.last_result

  const handleRunScraper = async (): Promise<void> => {
    if (isComingSoon) return
    console.log('[MorePortalsPage] Running scraper...')
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
    // Reset filters when switching portals
    setSelectedKeyword('all')
    setSelectedState('all')
    setKeywordFilter('')
  }

  // If coming soon, show the coming soon card
  if (isComingSoon) {
    return (
      <div className="p-6 max-w-6xl mx-auto space-y-6">
        <div>
          <h1 className="text-xl font-semibold text-slate-900" style={lufgaSemiboldStyle}>
            More Portals
          </h1>
        </div>
        
        <PortalTabs activePortal={activePortalId} onPortalChange={handlePortalChange} />
        
        <ComingSoonCard portal={currentPortal} />
      </div>
    )
  }

  return (
    <div className="p-6 max-w-6xl mx-auto space-y-6">
      <div>
        <h1 className="text-xl font-semibold text-slate-900" style={lufgaSemiboldStyle}>
          More Portals
        </h1>
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
                <div className={clsx(
                  'flex items-center gap-1.5 text-xs',
                  lastResult.success ? 'text-emerald-600' : 'text-red-500'
                )}>
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
              className="flex items-center gap-1 px-3 py-2 rounded-lg border border-slate-200 text-slate-600 hover:bg-slate-50 transition-colors text-sm"
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
                  <><Loader2 size={14} className="animate-spin" /> Starting...</>
                ) : (
                  <><Play size={14} /> Run Scraper</>
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

      {/* Filters */}
      <div className="bg-white rounded-xl border border-slate-200 p-4 space-y-3">
        <div className="flex flex-wrap items-center gap-3">
          <div className="flex items-center gap-1.5">
            <Filter size={14} className="text-slate-400" />
            <span className="text-xs text-slate-500" style={lufgaRegularStyle}>Filters:</span>
          </div>

          {/* Keyword filter dropdown */}
          <div className="flex items-center gap-1.5">
            <span className="text-xs text-slate-400">Keyword:</span>
            <select
              value={selectedKeyword}
              onChange={(e) => setSelectedKeyword(e.target.value)}
              className="text-xs border border-slate-200 rounded-lg px-2 py-1 focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white"
              style={lufgaRegularStyle}
            >
              <option value="all">All Keywords</option>
              {allKeywords.map((kw: string) => (
                <option key={kw} value={kw}>{kw}</option>
              ))}
            </select>
          </div>

          {/* State filter dropdown */}
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
                <option key={state} value={state}>{state}</option>
              ))}
            </select>
          </div>

          {/* Search input */}
          <div className="relative flex-1 min-w-[200px]">
            <Search size={14} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-slate-400" />
            <input
              type="text"
              placeholder="Search tenders..."
              value={keywordFilter}
              onChange={(e) => setKeywordFilter(e.target.value)}
              className="w-full pl-8 pr-8 py-1.5 border border-slate-200 rounded-lg text-xs focus:outline-none focus:ring-2 focus:ring-blue-500"
              style={lufgaRegularStyle}
            />
            {keywordFilter && (
              <button
                onClick={() => setKeywordFilter('')}
                className="absolute right-2 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600"
              >
                <X size={12} />
              </button>
            )}
          </div>

          {/* Result count */}
          <span className="text-xs text-slate-400 ml-auto" style={lufgaRegularStyle}>
            {isLoading ? 'Loading...' : `${filteredTenders.length} results`}
          </span>
        </div>
      </div>

      {/* Tenders from current portal */}
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
            {filteredTenders.map((tender: Tender18Tender) => (
              <Tender18Card key={tender.id} tender={tender} />
            ))}
          </div>
        )}
      </div>
    </div>
  )
}