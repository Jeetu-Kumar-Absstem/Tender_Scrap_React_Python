// src/pages/HospitalPage.tsx
// Add to router: <Route path="/hospitals" element={<HospitalPage />} />
import { useState, useEffect, useCallback, useRef } from 'react'
import {
  Hospital, Search, Download, RefreshCw,
  ChevronUp, ChevronDown, ChevronsLeft, ChevronsRight,
  ChevronLeft, ChevronRight,
  Globe, Phone, Mail, X, Loader2, Square,
} from 'lucide-react'
import { supabase } from '../lib/supabase'
import { clsx } from 'clsx'

// ── Static NABH state list ────────────────────────────────────
const NABH_STATES = [
  'Ahmedabad','Andhra Pradesh','Arunachal Pradesh','Assam',
  'Bagmati Zone','Bangalore','Bihar','Biratnagar','Chandigarh',
  'Chattisgarh','Chhattisgarh','Chitwan','Delhi','Gandaki Zone',
  'Goa','Gujarat','Gwarko','Haryana','Himachal Pradesh','Hyderabad',
  'Jammu and Kashmir','Jharkhand','Kanchanbari','Karnataka','Kathmandu',
  'Kerala','Kolkata','Koshi Zone','Lumbini','Lumbini Zone',
  'Madhya Pradesh','Maharashtra','Manipur','Mechi Zone','Meghalaya',
  'Mizoram','Morang','Nagaland','Narayani Zone','Nepalgunj',
  'New Delhi','Odisha','Orissa','Pokhara','Pondicherry','Puducherry',
  'Punjab','Rajasthan','Rani Gaon','Sikkim','Srinagar','Tamil Nadu',
  'Telangana','Tripura','Uttar Pradesh','Uttarakhand','West Bengal',
]

const PAGE_SIZE = 50

// ── Helpers to parse city/state out of address string ─────────
// Address format from NABH: "Street..., City, State, 6digitPIN"
function parseCityState(address: string | null): { city: string; state: string } {
  if (!address) return { city: '', state: '' }
  let addr = address.replace(/,?\s*\d{6}\s*\.?\s*$/, '').trim()
  addr = addr.replace(/,?\s*India\s*$/i, '').trim()
  const parts = addr.split(',').map(p => p.trim()).filter(Boolean)
  if (parts.length >= 2) return { state: parts[parts.length - 1], city: parts[parts.length - 2] }
  return { city: '', state: '' }
}

interface HospitalRow {
  id:               string
  name:             string
  address:          string | null
  phone:            string | null
  email:            string | null
  website:          string | null
  accreditation_no: string | null
  scraped_at:       string | null
}

type SortDir = 'asc' | 'desc'

// ── CSV download ──────────────────────────────────────────────
function downloadCSV(rows: HospitalRow[], state: string, city: string) {
  const header = ['Name','Address','Phone','Email','Website','Accreditation No'].join(',')
  const lines  = rows.map(h =>
    [h.name, h.address, h.phone, h.email, h.website, h.accreditation_no]
      .map(v => `"${(v ?? '').replace(/"/g, '""')}"`)
      .join(',')
  )
  const blob = new Blob([[header, ...lines].join('\n')], { type: 'text/csv;charset=utf-8;' })
  const url  = URL.createObjectURL(blob)
  const a    = Object.assign(document.createElement('a'), {
    href:     url,
    download: `nabh_${(state || 'all').replace(/\s+/g,'_')}${city ? `_${city.replace(/\s+/g,'_')}` : ''}.csv`,
  })
  a.click()
  URL.revokeObjectURL(url)
}

// ── PDF (browser print) ───────────────────────────────────────
function downloadPDF(rows: HospitalRow[], state: string, city: string) {
  const esc = (s: string) => s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')
  const trs = rows.map((h, i) => {
    const { city: c, state: s } = parseCityState(h.address)
    return `
    <tr style="background:${i%2?'#f9fafb':'#fff'}">
      <td>${i+1}</td>
      <td><strong>${esc(h.name)}</strong>${h.accreditation_no ? `<br/><code style="font-size:10px;color:#6b7280">${esc(h.accreditation_no)}</code>` : ''}</td>
      <td>${esc(c||'—')}</td><td>${esc(s||'—')}</td>
      <td>${esc(h.phone||'—')}</td><td>${esc(h.email||'—')}</td>
      <td>${h.website ? `<a href="${esc(h.website)}">${esc(h.website.replace(/^https?:\/\/(www\.)?/,'').slice(0,30))}</a>` : '—'}</td>
    </tr>`
  }).join('')
  const html = `<!DOCTYPE html><html><head><meta charset="utf-8">
    <title>NABH Hospitals — ${state||'All'}${city?` / ${city}`:''}</title>
    <style>
      body{font-family:Arial,sans-serif;font-size:11px;margin:20px}
      h2{font-size:15px;margin:0 0 4px}p{font-size:11px;color:#6b7280;margin:0 0 12px}
      table{border-collapse:collapse;width:100%}
      th{background:#1e40af;color:#fff;padding:6px 8px;text-align:left;font-size:10px}
      td{padding:5px 8px;border-bottom:1px solid #e5e7eb;vertical-align:top}
      a{color:#1e40af}@media print{body{margin:10mm}}
    </style></head><body>
    <h2>NABH Accredited Hospitals</h2>
    <p>State: <strong>${state||'All'}</strong> &nbsp;|&nbsp; City: <strong>${city||'All'}</strong> &nbsp;|&nbsp; Total: <strong>${rows.length.toLocaleString('en-IN')}</strong> &nbsp;|&nbsp; ${new Date().toLocaleString('en-IN')}</p>
    <table><thead><tr><th>#</th><th>Hospital</th><th>City</th><th>State</th><th>Phone</th><th>Email</th><th>Website</th></tr></thead>
    <tbody>${trs}</tbody></table></body></html>`
  const w = window.open('','_blank')
  if (!w) return
  w.document.write(html); w.document.close(); w.focus()
  setTimeout(() => w.print(), 400)
}

// ── Sort icon ─────────────────────────────────────────────────
function SortIcon({ active, dir }: { active: boolean; dir: SortDir }) {
  if (!active) return <ChevronUp size={10} className="text-slate-300 ml-0.5" />
  return dir === 'asc'
    ? <ChevronUp size={10} className="text-blue-600 ml-0.5" />
    : <ChevronDown size={10} className="text-blue-600 ml-0.5" />
}

// ── Main page ─────────────────────────────────────────────────
export default function HospitalPage() {
  const [selectedState, setSelectedState] = useState('')
  const [selectedCity,  setSelectedCity]  = useState('')
  const [searchQuery,   setSearchQuery]   = useState('')
  const [debouncedQ,    setDebouncedQ]    = useState('')

  const [hospitals,  setHospitals]  = useState<HospitalRow[]>([])
  const [cities,     setCities]     = useState<string[]>([])
  const [totalCount, setTotalCount] = useState(0)
  const [page,       setPage]       = useState(1)
  const [sortDir,    setSortDir]    = useState<SortDir>('asc')   // sort by name only

  const [loading,     setLoading]     = useState(false)
  const [cityLoading, setCityLoading] = useState(false)
  const [scraping,    setScraping]    = useState(false)
  const [scrapeMsg,   setScrapeMsg]   = useState('')
  const [scrapeErr,   setScrapeErr]   = useState('')
  const [dlLoading,   setDlLoading]   = useState<'csv'|'pdf'|null>(null)

  // AbortController ref to stop the scrape request
  const scrapeAbortRef = useRef<AbortController | null>(null)

  // Debounce search
  const debounceRef = useRef<ReturnType<typeof setTimeout>>()
  useEffect(() => {
    clearTimeout(debounceRef.current)
    debounceRef.current = setTimeout(() => { setDebouncedQ(searchQuery); setPage(1) }, 350)
    return () => clearTimeout(debounceRef.current)
  }, [searchQuery])

  // ── Load cities from NABH API when state changes ──────────
  // Mirrors test_cities.py: GET https://nabh.co/wp-admin/admin-ajax.php?action=get_cities_by_state&state=<STATE>
  // We proxy through /api/hospitals/cities?state=... to avoid CORS
  useEffect(() => {
    setSelectedCity('')
    setPage(1)
    setCities([])
    if (!selectedState) return

    setCityLoading(true)
    fetch(`/api/hospitals/cities?state=${encodeURIComponent(selectedState)}`)
      .then(r => r.json())
      .then((data: string[]) => {
        // data is a plain array of city name strings from the NABH API
        const cleaned = Array.from(new Set(
          data
            .map(c => (typeof c === 'string' ? c.trim() : ''))
            .filter(c => c.length > 1 && c.length < 40 && !/^\d/.test(c))
        )).sort()
        setCities(cleaned)
      })
      .catch(() => {
        // Fallback: derive cities from already-loaded hospital addresses
        setCities([])
      })
      .finally(() => setCityLoading(false))
  }, [selectedState])

  // ── Fetch hospitals from Supabase ─────────────────────────
  // Filtering by state and city is done via ILIKE on address column
  // since we no longer have separate city/state columns.
  const fetchHospitals = useCallback(async () => {
    setLoading(true)
    let q = supabase
      .from('nabh_hospitals')
      .select('*', { count: 'exact' })

    if (selectedState) q = q.ilike('address', `%${selectedState}%`)
    if (selectedCity)  q = q.ilike('address', `%${selectedCity}%`)
    if (debouncedQ.trim()) q = q.ilike('name', `%${debouncedQ.trim()}%`)

    q = q.order('name', { ascending: sortDir === 'asc' })
         .range((page-1)*PAGE_SIZE, page*PAGE_SIZE - 1)

    const { data, count } = await q
    setLoading(false)
    setHospitals((data as HospitalRow[]) ?? [])
    setTotalCount(count ?? 0)
  }, [selectedState, selectedCity, debouncedQ, page, sortDir])

  useEffect(() => { fetchHospitals() }, [fetchHospitals])

  // ── Fetch all rows for download ───────────────────────────
  const fetchAll = useCallback(async (): Promise<HospitalRow[]> => {
    let q = supabase.from('nabh_hospitals').select('*').order('name', { ascending: sortDir === 'asc' })
    if (selectedState) q = q.ilike('address', `%${selectedState}%`)
    if (selectedCity)  q = q.ilike('address', `%${selectedCity}%`)
    if (debouncedQ.trim()) q = q.ilike('name', `%${debouncedQ.trim()}%`)
    const { data } = await q
    return (data as HospitalRow[]) ?? []
  }, [selectedState, selectedCity, debouncedQ, sortDir])

  const handleSort = () => {
    setSortDir(d => d === 'asc' ? 'desc' : 'asc')
    setPage(1)
  }

  // ── Scraper — hardcoded Haryana, runs once ────────────────
  const handleScrape = async () => {
    const ctrl = new AbortController()
    scrapeAbortRef.current = ctrl
    setScraping(true)
    setScrapeMsg('Scraping Haryana hospitals from NABH and upserting to Supabase…')
    setScrapeErr('')
    try {
      const res = await fetch('/api/hospitals/scrape', {
        method:  'POST',
        headers: { 'Content-Type': 'application/json' },
        body:    JSON.stringify({ state: 'Haryana' }),   // hardcoded
        signal:  ctrl.signal,
      })
      if (!res.ok) throw new Error(`Server error ${res.status}`)
      const json = await res.json()
      setScrapeMsg(json.message ?? `✓ Done — ${json.inserted ?? '?'} Haryana hospitals upserted`)
      fetchHospitals()
    } catch (e: unknown) {
      if ((e as Error).name === 'AbortError') {
        setScrapeMsg('Scrape stopped by user. Partial data may have been saved.')
      } else {
        setScrapeErr(`Failed: ${(e as Error).message}`)
        setScrapeMsg('')
      }
    } finally {
      setScraping(false)
      scrapeAbortRef.current = null
    }
  }

  // ── Stop button ───────────────────────────────────────────
  const handleStop = () => {
    if (scrapeAbortRef.current) {
      scrapeAbortRef.current.abort()
    }
  }

  const handleDownload = async (type: 'csv'|'pdf') => {
    setDlLoading(type)
    const all = await fetchAll()
    if (type === 'csv') downloadCSV(all, selectedState, selectedCity)
    else                downloadPDF(all, selectedState, selectedCity)
    setDlLoading(null)
  }

  const clearFilters = () => { setSelectedState(''); setSelectedCity(''); setSearchQuery(''); setPage(1) }
  const hasFilters   = selectedState || selectedCity || searchQuery
  const totalPages   = Math.max(1, Math.ceil(totalCount / PAGE_SIZE))

  // ── Render ────────────────────────────────────────────────
  return (
    <div className="p-6 space-y-4 min-h-full">

      {/* ── Page header ── */}
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div>
          <h1 className="text-xl font-semibold text-slate-900 flex items-center gap-2">
            <Hospital size={18} className="text-blue-600" />
            Hospital Data
          </h1>
          <p className="text-sm text-slate-500 mt-0.5">
            {totalCount > 0
              ? `${totalCount.toLocaleString('en-IN')} NABH-accredited hospitals`
              : 'NABH-accredited hospital directory'}
          </p>
        </div>

        <div className="flex items-center gap-2 flex-wrap">
          {/* Download buttons */}
          <button
            onClick={() => handleDownload('csv')}
            disabled={dlLoading !== null || totalCount === 0}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-lg border border-slate-200 bg-white text-slate-600 hover:bg-slate-50 hover:border-slate-300 transition-all disabled:opacity-40 disabled:cursor-not-allowed"
          >
            {dlLoading === 'csv' ? <Loader2 size={11} className="animate-spin" /> : <Download size={11} />}
            CSV
          </button>
          <button
            onClick={() => handleDownload('pdf')}
            disabled={dlLoading !== null || totalCount === 0}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-lg border border-slate-200 bg-white text-slate-600 hover:bg-slate-50 hover:border-slate-300 transition-all disabled:opacity-40 disabled:cursor-not-allowed"
          >
            {dlLoading === 'pdf' ? <Loader2 size={11} className="animate-spin" /> : <Download size={11} />}
            PDF
          </button>

          {/* Refresh */}
          <button
            onClick={fetchHospitals}
            disabled={loading}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-lg border border-slate-200 bg-white text-slate-600 hover:bg-slate-50 transition-all disabled:opacity-40"
          >
            <RefreshCw size={11} className={clsx(loading && 'animate-spin')} />
            Refresh
          </button>

          {/* Scraper + Stop */}
          {!scraping ? (
            <button
              onClick={handleScrape}
              className="flex items-center gap-1.5 px-3 py-2 text-sm font-medium rounded-lg bg-blue-600 text-white hover:bg-blue-700 shadow-sm hover:shadow transition-all"
            >
              <RefreshCw size={13} /> Run Scraper
            </button>
          ) : (
            <div className="flex items-center gap-2">
              <span className="flex items-center gap-1.5 px-3 py-2 text-sm font-medium rounded-lg bg-blue-100 text-blue-500 cursor-default">
                <Loader2 size={13} className="animate-spin" /> Scraping…
              </span>
              <button
                onClick={handleStop}
                title="Stop scraper"
                className="flex items-center gap-1.5 px-3 py-2 text-sm font-medium rounded-lg bg-red-100 text-red-600 hover:bg-red-200 transition-all"
              >
                <Square size={13} className="fill-red-600" /> Stop
              </button>
            </div>
          )}
        </div>
      </div>

      {/* ── Scraper status banners ── */}
      {scrapeMsg && (
        <div className="flex items-start justify-between gap-2 px-4 py-3 bg-blue-50 border border-blue-200 rounded-lg text-sm text-blue-700">
          <span>{scrapeMsg}</span>
          <button onClick={() => setScrapeMsg('')}><X size={13} className="text-blue-400 hover:text-blue-600 mt-0.5" /></button>
        </div>
      )}
      {scrapeErr && (
        <div className="flex items-start justify-between gap-2 px-4 py-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700">
          <span>{scrapeErr}</span>
          <button onClick={() => setScrapeErr('')}><X size={13} className="text-red-400 hover:text-red-600 mt-0.5" /></button>
        </div>
      )}

      {/* ── Filter bar ── */}
      <div className="flex items-center gap-2 flex-wrap">

        {/* State */}
        <select
          value={selectedState}
          onChange={e => { setSelectedState(e.target.value); setPage(1) }}
          className="px-3 py-2 text-sm rounded-lg border border-slate-200 bg-white text-slate-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent min-w-[180px]"
        >
          <option value="">All States</option>
          {NABH_STATES.map(s => <option key={s} value={s}>{s}</option>)}
        </select>

        {/* City — populated from NABH API once a state is chosen */}
        <div className="relative">
          <select
            value={selectedCity}
            onChange={e => { setSelectedCity(e.target.value); setPage(1) }}
            disabled={!selectedState || cityLoading}
            className="px-3 py-2 text-sm rounded-lg border border-slate-200 bg-white text-slate-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent min-w-[180px] disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <option value="">
              {!selectedState
                ? 'Select state first'
                : cityLoading
                  ? 'Loading cities…'
                  : `All Cities (${cities.length})`}
            </option>
            {cities.map(c => <option key={c} value={c}>{c}</option>)}
          </select>
          {cityLoading && (
            <Loader2 size={12} className="animate-spin absolute right-8 top-1/2 -translate-y-1/2 text-slate-400 pointer-events-none" />
          )}
        </div>

        {/* Search */}
        <div className="relative flex-1 min-w-[200px]">
          <Search size={13} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400 pointer-events-none" />
          <input
            type="text"
            placeholder="Search hospital name…"
            value={searchQuery}
            onChange={e => setSearchQuery(e.target.value)}
            className="w-full pl-8 pr-3 py-2 text-sm rounded-lg border border-slate-200 bg-white text-slate-700 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
          />
        </div>

        {/* Clear */}
        {hasFilters && (
          <button
            onClick={clearFilters}
            className="flex items-center gap-1 px-3 py-2 text-xs font-medium text-slate-500 hover:text-slate-700 border border-slate-200 rounded-lg bg-white hover:bg-slate-50 transition-all"
          >
            <X size={11} /> Clear
          </button>
        )}
      </div>

      {/* ── Table card ── */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm border-collapse">
            <thead>
              <tr className="border-b border-slate-200 bg-slate-50">
                {/* Sortable name column */}
                <th
                  onClick={handleSort}
                  className="px-4 py-3 text-left text-[11px] font-semibold text-slate-500 uppercase tracking-wider cursor-pointer hover:text-slate-700 select-none whitespace-nowrap"
                >
                  <span className="flex items-center gap-0.5">
                    Hospital Name <SortIcon active dir={sortDir} />
                  </span>
                </th>
                <th className="px-4 py-3 text-left text-[11px] font-semibold text-slate-500 uppercase tracking-wider whitespace-nowrap">City</th>
                <th className="px-4 py-3 text-left text-[11px] font-semibold text-slate-500 uppercase tracking-wider whitespace-nowrap">State</th>
                <th className="px-4 py-3 text-left text-[11px] font-semibold text-slate-500 uppercase tracking-wider whitespace-nowrap">Phone</th>
                <th className="px-4 py-3 text-left text-[11px] font-semibold text-slate-500 uppercase tracking-wider whitespace-nowrap">Email</th>
                <th className="px-4 py-3 text-left text-[11px] font-semibold text-slate-500 uppercase tracking-wider whitespace-nowrap">Website</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {loading ? (
                <tr>
                  <td colSpan={6} className="py-16 text-center text-slate-400 text-sm">
                    <Loader2 size={18} className="animate-spin mx-auto mb-2 text-blue-500" />
                    Loading hospitals…
                  </td>
                </tr>
              ) : hospitals.length === 0 ? (
                <tr>
                  <td colSpan={6} className="py-16 text-center">
                    <Hospital size={28} className="mx-auto mb-2 text-slate-300" />
                    <p className="text-slate-500 text-sm font-medium">No hospitals found</p>
                    <p className="text-slate-400 text-xs mt-1">
                      {hasFilters ? 'Try adjusting your filters' : 'Click "Run Scraper" to populate the database'}
                    </p>
                  </td>
                </tr>
              ) : (
                hospitals.map((h, i) => {
                  const { city, state } = parseCityState(h.address)
                  return (
                    <tr
                      key={h.id}
                      className={clsx('hover:bg-blue-50/40 transition-colors', i % 2 === 1 && 'bg-slate-50/50')}
                    >
                      {/* Name + accreditation + address */}
                      <td className="px-4 py-3 max-w-xs">
                        <div className="font-medium text-slate-900 text-sm leading-snug">{h.name}</div>
                        {h.accreditation_no && (
                          <span className="inline-block mt-1 px-1.5 py-0.5 bg-blue-50 text-blue-600 text-[10px] font-mono rounded">
                            {h.accreditation_no}
                          </span>
                        )}
                        {h.address && (
                          <div className="text-[11px] text-slate-400 mt-1 leading-relaxed line-clamp-2">{h.address}</div>
                        )}
                      </td>
                      {/* City and State parsed from address at render time */}
                      <td className="px-4 py-3 text-slate-600 whitespace-nowrap">{city || '—'}</td>
                      <td className="px-4 py-3 text-slate-600 whitespace-nowrap">{state || '—'}</td>
                      <td className="px-4 py-3 whitespace-nowrap">
                        {h.phone
                          ? <a href={`tel:${h.phone}`} className="flex items-center gap-1 text-slate-600 hover:text-blue-600 transition-colors text-xs">
                              <Phone size={10} className="text-slate-400" />{h.phone}
                            </a>
                          : <span className="text-slate-300">—</span>}
                      </td>
                      <td className="px-4 py-3">
                        {h.email
                          ? <a href={`mailto:${h.email}`} className="flex items-center gap-1 text-blue-600 hover:text-blue-800 transition-colors text-xs max-w-[180px] truncate">
                              <Mail size={10} className="flex-shrink-0" /><span className="truncate">{h.email}</span>
                            </a>
                          : <span className="text-slate-300">—</span>}
                      </td>
                      <td className="px-4 py-3">
                        {h.website
                          ? <a href={h.website} target="_blank" rel="noopener noreferrer"
                              className="flex items-center gap-1 text-blue-600 hover:text-blue-800 transition-colors text-xs max-w-[160px]"
                              title={h.website}>
                              <Globe size={10} className="flex-shrink-0" />
                              <span className="truncate">
                                {(() => { try { return new URL(h.website).hostname.replace('www.','') } catch { return h.website.slice(0,25) } })()}
                              </span>
                            </a>
                          : <span className="text-slate-300">—</span>}
                      </td>
                    </tr>
                  )
                })
              )}
            </tbody>
          </table>
        </div>

        {/* ── Pagination footer ── */}
        {!loading && totalCount > 0 && (
          <div className="flex items-center justify-between px-4 py-3 border-t border-slate-100 bg-slate-50/50">
            <p className="text-xs text-slate-500">
              Showing {((page-1)*PAGE_SIZE)+1}–{Math.min(page*PAGE_SIZE, totalCount)} of{' '}
              <strong>{totalCount.toLocaleString('en-IN')}</strong> hospitals
            </p>
            <div className="flex items-center gap-1">
              <button onClick={() => setPage(1)} disabled={page===1}
                className="p-1.5 rounded hover:bg-slate-200 disabled:opacity-30 disabled:cursor-not-allowed transition-colors">
                <ChevronsLeft size={13} className="text-slate-600" />
              </button>
              <button onClick={() => setPage(p => p-1)} disabled={page===1}
                className="p-1.5 rounded hover:bg-slate-200 disabled:opacity-30 disabled:cursor-not-allowed transition-colors">
                <ChevronLeft size={13} className="text-slate-600" />
              </button>
              <span className="px-3 py-1 text-xs text-slate-600 font-medium">
                {page} / {totalPages}
              </span>
              <button onClick={() => setPage(p => p+1)} disabled={page===totalPages}
                className="p-1.5 rounded hover:bg-slate-200 disabled:opacity-30 disabled:cursor-not-allowed transition-colors">
                <ChevronRight size={13} className="text-slate-600" />
              </button>
              <button onClick={() => setPage(totalPages)} disabled={page===totalPages}
                className="p-1.5 rounded hover:bg-slate-200 disabled:opacity-30 disabled:cursor-not-allowed transition-colors">
                <ChevronsRight size={13} className="text-slate-600" />
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}