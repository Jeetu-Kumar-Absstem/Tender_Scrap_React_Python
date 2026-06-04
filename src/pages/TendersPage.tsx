// src/pages/TendersPage.tsx
import { useEffect, useRef, useState, useCallback } from 'react'
import { useTenders } from '../hooks/useTenders'
import TenderCard from '../components/tenders/TenderCard'
import { Search, SlidersHorizontal, X, Loader2 } from 'lucide-react'
import type { TenderFilters, SiteType, UserStatus } from '../types/tender'
import { useInView } from '../hooks/useInView'

const KEYWORDS = [
  'psa plant',
  'psa oxygen plant',
  'psa oxygen generation plant',
  'pressure swing adsorption oxygen',
  'medical oxygen generation plant',
  'oxygen plant sitc',
  'on-site oxygen generation',
  'oxygen generator plant',
  'oxygen gas generator',
  'psa oxygen',
  'psa nitrogen plant',
  'psa nitrogen generator',
  'pressure swing adsorption nitrogen',
  'nitrogen generation plant',
  'nitrogen plant sitc',
  'on-site nitrogen generation',
  'nitrogen gas generator',
  'psa nitrogen',
  'amc psa oxygen plant',
  'cmc psa oxygen plant',
  'annual maintenance contract oxygen plant',
  'camc psa',
  'comprehensive maintenance contract',
  'preventive maintenance oxygen generator',
  'service contract psa plant',
  'breakdown maintenance oxygen plant',
  'psa plant amc',
  'psa plant cmc',
  'medical gas plant maintenance',
  'oxygen nitrogen plant service contract',
  'mgps maintenance',
  'psa plant spare parts',
  'oxygen plant repair maintenance',
  'vpsa',
  'liquid oxygen',
  'lox',
  'concentrator',
  'o2 plant',
  'gas plant',
  'gas generation',
]

export default function TendersPage() {
  const [filters, setFilters] = useState<TenderFilters>({ user_status: 'all' })
  const [showFilters, setShowFilters] = useState(false)
  const [search, setSearch] = useState('')
  const [selectedKeywords, setSelectedKeywords] = useState<string[]>([])
  const [showKeywordDropdown, setShowKeywordDropdown] = useState(false)
  const [keywordQuery, setKeywordQuery] = useState('')
  const keywordFilterRef = useRef<HTMLDivElement | null>(null)

  const { data, isLoading, isFetchingNextPage, fetchNextPage, hasNextPage } = useTenders(filters)
  const allTenders = data?.pages.flatMap(p => p.tenders) ?? []
  const total = data?.pages[0]?.total ?? 0
  const visibleTenders = selectedKeywords.length
    ? allTenders.filter(t => selectedKeywords.every(keyword => t.keywords_matched?.includes(keyword)))
    : allTenders
  const displayedCount = selectedKeywords.length ? visibleTenders.length : total

  const sentinelRef = useInView(() => {
    if (hasNextPage && !isFetchingNextPage) fetchNextPage()
  })

  const applySearch = useCallback(() => {
    setFilters(f => ({ ...f, search: search || undefined }))
  }, [search])

  const activeFilters = Object.entries(filters).filter(([k, v]) =>
    v !== undefined && !(k === 'user_status' && v === 'all')
  )

  const filteredKeywords = KEYWORDS.filter(keyword =>
    keyword.toLowerCase().includes(keywordQuery.trim().toLowerCase())
  )

  const toggleKeyword = (keyword: string) => {
    setSelectedKeywords(prev =>
      prev.includes(keyword)
        ? prev.filter(item => item !== keyword)
        : [...prev, keyword]
    )
  }

  const clearAll = () => {
    setFilters({ user_status: 'all' })
    setSearch('')
    setSelectedKeywords([])
    setKeywordQuery('')
    setShowKeywordDropdown(false)
  }

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (!keywordFilterRef.current) return
      if (!keywordFilterRef.current.contains(event.target as Node)) {
        setShowKeywordDropdown(false)
      }
    }

    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  return (
    <div className="p-6 max-w-5xl mx-auto space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-slate-900">Tenders</h1>
          <p className="text-sm text-slate-500 mt-0.5">{displayedCount.toLocaleString()} results</p>
        </div>
        <button
          onClick={() => setShowFilters(v => !v)}
          className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm border transition-colors ${showFilters ? 'bg-blue-50 text-blue-700 border-blue-200' : 'bg-white text-slate-600 border-slate-200 hover:border-slate-300'}`}
        >
          <SlidersHorizontal size={13} />
          Filters
          {(activeFilters.length + selectedKeywords.length) > 0 && (
            <span className="bg-blue-600 text-white text-[10px] rounded-full w-4 h-4 flex items-center justify-center">
              {activeFilters.length + selectedKeywords.length}
            </span>
          )}
        </button>
      </div>

      <div className="flex gap-2">
        <div className="flex-1 relative">
          <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
          <input
            type="text" value={search}
            onChange={e => setSearch(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && applySearch()}
            placeholder="Search by title, org, reference number..."
            className="w-full pl-8 pr-3 py-2 text-sm border border-slate-200 rounded-lg bg-white focus:outline-none focus:border-blue-400"
          />
        </div>
        <button onClick={applySearch} className="px-4 py-2 bg-blue-600 text-white text-sm rounded-lg hover:bg-blue-700 transition-colors">Search</button>
      </div>

      {showFilters && (
        <div className="bg-white border border-slate-200 rounded-xl p-4 grid grid-cols-1 md:grid-cols-5 gap-3">
          <div>
            <label className="text-xs font-medium text-slate-500 block mb-1">Site Type</label>
            <select value={filters.site_type ?? ''} onChange={e => setFilters(f => ({ ...f, site_type: e.target.value as SiteType || undefined }))}
              className="w-full text-sm border border-slate-200 rounded-lg px-2 py-1.5 bg-white focus:outline-none">
              <option value="">All types</option>
              <option value="A">Type A — Static</option>
              <option value="B">Type B — JS</option>
              <option value="C">Type C — JS</option>
            </select>
          </div>
          <div className="relative" ref={keywordFilterRef}>
            <label className="text-xs font-medium text-slate-500 block mb-1">Keyword</label>
            <button
              type="button"
              onClick={() => setShowKeywordDropdown(v => !v)}
              className="w-full flex items-center justify-between gap-2 text-sm border border-slate-200 rounded-lg px-2.5 py-2 bg-white focus:outline-none hover:border-slate-300"
            >
              <span className={selectedKeywords.length === 0 ? 'text-slate-400' : 'text-slate-700'}>
                {selectedKeywords.length === 0
                  ? 'No Filter'
                  : `${selectedKeywords.length} keyword${selectedKeywords.length > 1 ? 's' : ''} selected`}
              </span>
              <span className="text-slate-400">▾</span>
            </button>

            {showKeywordDropdown && (
              <div className="absolute left-0 right-0 z-20 mt-1 rounded-lg border border-slate-200 bg-white shadow-lg">
                <div className="p-3 border-b border-slate-100">
                  <input
                    type="text"
                    value={keywordQuery}
                    onChange={e => setKeywordQuery(e.target.value)}
                    placeholder="Search keywords..."
                    className="w-full text-sm border border-slate-200 rounded-md px-2 py-1.5 bg-white focus:outline-none focus:border-blue-400"
                  />
                </div>
                <div className="max-h-56 overflow-auto px-3 py-2 space-y-2">
                  <button
                    type="button"
                    onClick={() => {
                      setSelectedKeywords([])
                      setKeywordQuery('')
                      setShowKeywordDropdown(false)
                    }}
                    className="w-full text-left text-sm text-slate-600 hover:text-slate-900 px-2 py-1 rounded hover:bg-slate-50"
                  >
                    No Filter
                  </button>
                  {filteredKeywords.length === 0 ? (
                    <div className="text-xs text-slate-400 px-2 py-2">No keywords found.</div>
                  ) : (
                    filteredKeywords.map(keyword => (
                      <label key={keyword} className="flex items-start gap-2 text-sm text-slate-700 cursor-pointer px-2 py-1 rounded hover:bg-slate-50">
                        <input
                          type="checkbox"
                          checked={selectedKeywords.includes(keyword)}
                          onChange={() => {
                            toggleKeyword(keyword)
                            setShowKeywordDropdown(false)
                          }}
                          className="mt-0.5 h-4 w-4 rounded border-slate-300 text-blue-600 focus:ring-blue-500"
                        />
                        <span className="leading-5">{keyword}</span>
                      </label>
                    ))
                  )}
                </div>
              </div>
            )}
          </div>
          <div>
            <label className="text-xs font-medium text-slate-500 block mb-1">Deadline from</label>
            <input type="date" value={filters.deadline_after ?? ''} onChange={e => setFilters(f => ({ ...f, deadline_after: e.target.value || undefined }))}
              className="w-full text-sm border border-slate-200 rounded-lg px-2 py-1.5 bg-white focus:outline-none" />
          </div>
          <div>
            <label className="text-xs font-medium text-slate-500 block mb-1">Deadline to</label>
            <input type="date" value={filters.deadline_before ?? ''} onChange={e => setFilters(f => ({ ...f, deadline_before: e.target.value || undefined }))}
              className="w-full text-sm border border-slate-200 rounded-lg px-2 py-1.5 bg-white focus:outline-none" />
          </div>

          {/* Status filter */}
          <div>
            <label className="text-xs font-medium text-slate-500 block mb-1">Status</label>
            <select
              value={filters.user_status ?? 'all'}
              onChange={e => setFilters(f => ({ ...f, user_status: e.target.value as UserStatus | 'all' }))}
              className="w-full text-sm border border-slate-200 rounded-lg px-2 py-1.5 bg-white focus:outline-none"
            >
              <option value="all">All</option>
              <option value="active">Active</option>
              <option value="starred">★ Starred</option>
              <option value="done">✓ Done</option>
            </select>
          </div>
        </div>
      )}

      {(activeFilters.length > 0 || selectedKeywords.length > 0) && (
        <div className="flex flex-wrap gap-2">
          {activeFilters.map(([key, val]) => (
            <span key={key} className="inline-flex items-center gap-1 text-xs bg-blue-50 text-blue-700 border border-blue-200 px-2 py-1 rounded-full">
              {key}: {String(val)}
              <button onClick={() => setFilters(f => {
                const n = { ...f }
                if (key === 'user_status') n.user_status = 'all'
                else delete n[key as keyof TenderFilters]
                return n
              })}><X size={10} /></button>
            </span>
          ))}
          {selectedKeywords.map(keyword => (
            <span key={keyword} className="inline-flex items-center gap-1 text-xs bg-blue-50 text-blue-700 border border-blue-200 px-2 py-1 rounded-full">
              keyword: {keyword}
              <button onClick={() => setSelectedKeywords(prev => prev.filter(item => item !== keyword))}>
                <X size={10} />
              </button>
            </span>
          ))}
          <button onClick={clearAll} className="text-xs text-slate-500 hover:text-slate-700 px-2 py-1">Clear all</button>
        </div>
      )}

      {isLoading ? (
        <div className="flex items-center justify-center py-16">
          <Loader2 size={20} className="animate-spin text-blue-500" />
          <span className="ml-2 text-sm text-slate-500">Loading tenders...</span>
        </div>
      ) : visibleTenders.length === 0 ? (
        <div className="text-center py-16"><p className="text-slate-400 text-sm">No tenders found.</p></div>
      ) : (
        <div className="space-y-3">
          {visibleTenders.map(t => <TenderCard key={t.id} tender={t} />)}
          <div ref={sentinelRef} className="py-4 flex justify-center">
            {isFetchingNextPage && <Loader2 size={16} className="animate-spin text-blue-400" />}
          </div>
        </div>
      )}
    </div>
  )
}
