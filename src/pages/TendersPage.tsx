// src/pages/TendersPage.tsx
import { useState, useCallback } from 'react'
import { useTenders } from '../hooks/useTenders'
import TenderCard from '../components/tenders/TenderCard'
import { Search, SlidersHorizontal, X, Loader2 } from 'lucide-react'
import type { TenderFilters, SiteType } from '../types/tender'
import { useInView } from '../hooks/useInView'

const KEYWORDS = ['oxygen', 'psa', 'nitrogen', 'amc', 'cmc', 'medical gas', 'lox']

export default function TendersPage() {
  const [filters, setFilters] = useState<TenderFilters>({})
  const [showFilters, setShowFilters] = useState(false)
  const [search, setSearch] = useState('')

  const { data, isLoading, isFetchingNextPage, fetchNextPage, hasNextPage } = useTenders(filters)
  const allTenders = data?.pages.flatMap(p => p.tenders) ?? []
  const total = data?.pages[0]?.total ?? 0

  const sentinelRef = useInView(() => {
    if (hasNextPage && !isFetchingNextPage) fetchNextPage()
  })

  const applySearch = useCallback(() => {
    setFilters(f => ({ ...f, search: search || undefined }))
  }, [search])

  const activeFilters = Object.entries(filters).filter(([, v]) => v !== undefined)

  return (
    <div className="p-6 max-w-5xl mx-auto space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-slate-900">Tenders</h1>
          <p className="text-sm text-slate-500 mt-0.5">{total.toLocaleString()} results</p>
        </div>
        <button
          onClick={() => setShowFilters(v => !v)}
          className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm border transition-colors ${showFilters ? 'bg-blue-50 text-blue-700 border-blue-200' : 'bg-white text-slate-600 border-slate-200 hover:border-slate-300'}`}
        >
          <SlidersHorizontal size={13} />
          Filters
          {activeFilters.length > 0 && (
            <span className="bg-blue-600 text-white text-[10px] rounded-full w-4 h-4 flex items-center justify-center">{activeFilters.length}</span>
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
        <div className="bg-white border border-slate-200 rounded-xl p-4 grid grid-cols-2 md:grid-cols-4 gap-3">
          <div>
            <label className="text-xs font-medium text-slate-500 block mb-1">Site Type</label>
            <select value={filters.site_type ?? ''} onChange={e => setFilters(f => ({ ...f, site_type: e.target.value as SiteType || undefined }))}
              className="w-full text-sm border border-slate-200 rounded-lg px-2 py-1.5 bg-white focus:outline-none">
              <option value="">All types</option>
              <option value="A">Type A — Static</option>
              <option value="B">Type B — JS</option>
              <option value="C">Type C — API</option>
            </select>
          </div>
          <div>
            <label className="text-xs font-medium text-slate-500 block mb-1">Keyword</label>
            <select value={filters.keyword ?? ''} onChange={e => setFilters(f => ({ ...f, keyword: e.target.value || undefined }))}
              className="w-full text-sm border border-slate-200 rounded-lg px-2 py-1.5 bg-white focus:outline-none">
              <option value="">All</option>
              {KEYWORDS.map(k => <option key={k} value={k}>{k}</option>)}
            </select>
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
        </div>
      )}

      {activeFilters.length > 0 && (
        <div className="flex flex-wrap gap-2">
          {activeFilters.map(([key, val]) => (
            <span key={key} className="inline-flex items-center gap-1 text-xs bg-blue-50 text-blue-700 border border-blue-200 px-2 py-1 rounded-full">
              {key}: {String(val)}
              <button onClick={() => setFilters(f => { const n = { ...f }; delete n[key as keyof TenderFilters]; return n })}><X size={10} /></button>
            </span>
          ))}
          <button onClick={() => { setFilters({}); setSearch('') }} className="text-xs text-slate-500 hover:text-slate-700 px-2 py-1">Clear all</button>
        </div>
      )}

      {isLoading ? (
        <div className="flex items-center justify-center py-16">
          <Loader2 size={20} className="animate-spin text-blue-500" />
          <span className="ml-2 text-sm text-slate-500">Loading tenders...</span>
        </div>
      ) : allTenders.length === 0 ? (
        <div className="text-center py-16"><p className="text-slate-400 text-sm">No tenders found.</p></div>
      ) : (
        <div className="space-y-3">
          {allTenders.map(t => <TenderCard key={t.id} tender={t} />)}
          <div ref={sentinelRef} className="py-4 flex justify-center">
            {isFetchingNextPage && <Loader2 size={16} className="animate-spin text-blue-400" />}
          </div>
        </div>
      )}
    </div>
  )
}
