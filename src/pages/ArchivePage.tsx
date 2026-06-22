// src/pages/ArchivePage.tsx
import { useState, useMemo } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  ArrowLeft, Archive, ExternalLink, Calendar, MapPin,
  Building2, Search, X, Filter, ChevronDown, Loader2, Globe,
  Trash2, AlertTriangle,
} from 'lucide-react'
import { format, parseISO } from 'date-fns'
import { clsx } from 'clsx'
import { useArchiveTender18Tenders } from '../hooks/useArchiveTender18'
import type { ArchivedTender } from '../hooks/useArchiveTender18'
import { PORTALS } from '../config/portals'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { supabase } from '../lib/supabase'

const lufgaRegularStyle  = { fontFamily: "'Lufga', sans-serif", fontWeight: 400 } as const
const lufgaSemiboldStyle = { fontFamily: "'Lufga', sans-serif", fontWeight: 600 } as const

// eslint-disable-next-line @typescript-eslint/no-explicit-any
const db = supabase as any

// ─── helpers ────────────────────────────────────────────────────────────────

function extractState(location: string | null): string {
  if (!location) return 'Unknown'
  const states = [
    'Andaman','Andhra','Arunachal','Assam','Bihar','Chandigarh',
    'Chhattisgarh','Dadra','Daman','Delhi','Goa','Gujarat',
    'Haryana','Himachal','Jammu','Jharkhand','Karnataka','Kerala',
    'Ladakh','Lakshadweep','Madhya','Maharashtra','Manipur','Meghalaya',
    'Mizoram','Nagaland','Odisha','Puducherry','Punjab','Rajasthan',
    'Sikkim','Tamil','Telangana','Tripura','Uttar','Uttarakhand','West Bengal',
  ]
  for (const s of states) {
    if (location.toLowerCase().includes(s.toLowerCase())) return s
  }
  return 'Other'
}

const REASON_LABELS: Record<string, { label: string; color: string }> = {
  expired:          { label: 'Expired',     color: 'bg-red-50 text-red-600 border-red-200'         },
  manual_delete:    { label: 'Deleted',      color: 'bg-slate-100 text-slate-600 border-slate-200'  },
  pipeline_cleanup: { label: 'Auto-cleaned', color: 'bg-orange-50 text-orange-600 border-orange-200'},
}

// ─── delete hook ─────────────────────────────────────────────────────────────

function useDeleteArchiveTender() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (id: string) => {
      const { error } = await db
        .from('archive_tender18_tenders')
        .delete()
        .eq('id', id)
      if (error) throw new Error(error.message)
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['archive-tender18-tenders'] })
    },
  })
}

// ─── row component ───────────────────────────────────────────────────────────

function ArchiveRow({ tender }: { tender: ArchivedTender }) {
  const [confirmDelete, setConfirmDelete] = useState(false)
  const deleteMutation = useDeleteArchiveTender()
  const reason = REASON_LABELS[tender.archive_reason] ?? {
    label: tender.archive_reason,
    color: 'bg-slate-100 text-slate-600 border-slate-200',
  }

  const handleDelete = () => {
    deleteMutation.mutate(tender.id, {
      onSuccess: () => setConfirmDelete(false),
    })
  }

  return (
    <>
      <tr className="border-b border-slate-100 hover:bg-slate-50/60 transition-colors group">
        {/* Title + ref */}
        <td className="px-4 py-3 max-w-xs">
          <p className="text-sm font-medium text-slate-800 line-clamp-2 leading-snug">
            {tender.title ?? 'Untitled Tender'}
          </p>
          {tender.reference_number && (
            <p className="text-[11px] font-mono text-slate-400 mt-0.5 truncate">
              {tender.reference_number.slice(0, 35)}
            </p>
          )}
          <div className="flex flex-wrap gap-1 mt-1">
            {(tender.keywords_matched ?? []).slice(0, 3).map(kw => (
              <span key={kw} className="text-[10px] bg-blue-50 text-blue-600 px-1.5 py-0.5 rounded font-medium uppercase tracking-wide">
                {kw}
              </span>
            ))}
          </div>
        </td>

        {/* Organisation */}
        <td className="px-4 py-3 text-xs text-slate-600 max-w-[160px]">
          {tender.organization
            ? <span className="flex items-start gap-1"><Building2 size={11} className="mt-0.5 flex-shrink-0 text-slate-400" />{tender.organization}</span>
            : <span className="text-slate-300">—</span>}
        </td>

        {/* State */}
        <td className="px-4 py-3 text-xs text-slate-600 whitespace-nowrap">
          {tender.location
            ? <span className="flex items-center gap-1"><MapPin size={11} className="text-slate-400" />{extractState(tender.location)}</span>
            : <span className="text-slate-300">—</span>}
        </td>

        {/* Deadline */}
        <td className="px-4 py-3 text-xs text-slate-500 whitespace-nowrap">
          {tender.deadline
            ? <span className="flex items-center gap-1"><Calendar size={11} className="text-slate-400" />{format(parseISO(tender.deadline), 'dd MMM yyyy')}</span>
            : <span className="text-slate-300">—</span>}
        </td>

        {/* Value */}
        <td className="px-4 py-3 text-xs font-medium text-slate-700 whitespace-nowrap">
          {tender.estimated_value ? `₹${tender.estimated_value}` : <span className="text-slate-300">—</span>}
        </td>

        {/* Reason badge */}
        <td className="px-4 py-3 whitespace-nowrap">
          <span className={clsx('text-[11px] font-medium px-2 py-0.5 rounded border', reason.color)}>
            {reason.label}
          </span>
        </td>

        {/* Archived at */}
        <td className="px-3 py-3 text-xs text-slate-400 whitespace-nowrap">
          {format(parseISO(tender.archived_at), 'dd MMM yyyy, HH:mm')}
        </td>

        {/* Actions — always visible, sticky right */}
        <td className="px-3 py-3 whitespace-nowrap sticky right-0 bg-white group-hover:bg-slate-50/60 border-l border-slate-100 shadow-[-4px_0_6px_-2px_rgba(0,0,0,0.04)]">
          <div className="flex items-center gap-1.5">
            {tender.source_url && (
              <button
                onClick={() => window.open(tender.source_url!, '_blank', 'noopener,noreferrer')}
                className="flex items-center gap-1 text-[11px] text-blue-600 hover:text-blue-800 bg-blue-50 hover:bg-blue-100 px-2 py-1 rounded transition-colors"
              >
                <ExternalLink size={10} /> Open
              </button>
            )}
            <button
              onClick={() => setConfirmDelete(true)}
              className="flex items-center gap-1 text-[11px] text-red-500 hover:text-red-700 bg-red-50 hover:bg-red-100 px-2 py-1 rounded transition-colors"
              title="Permanently delete"
            >
              <Trash2 size={10} />
            </button>
          </div>
        </td>
      </tr>

      {/* Inline confirm row */}
      {confirmDelete && (
        <tr className="bg-red-50 border-b border-red-100">
          <td colSpan={8} className="px-4 py-2 sticky left-0">
            <div className="flex items-center justify-between gap-3">
              <div className="flex items-center gap-2 text-xs text-red-700">
                <AlertTriangle size={13} className="flex-shrink-0" />
                <span>Permanently delete this archived tender? This cannot be undone.</span>
              </div>
              <div className="flex items-center gap-1.5 flex-shrink-0">
                <button
                  onClick={() => setConfirmDelete(false)}
                  className="flex items-center gap-1 text-xs px-2 py-1 rounded bg-white border border-slate-200 text-slate-600 hover:bg-slate-50"
                >
                  <X size={10} /> Cancel
                </button>
                <button
                  onClick={handleDelete}
                  disabled={deleteMutation.isPending}
                  className="flex items-center gap-1 text-xs px-2 py-1 rounded bg-red-600 text-white hover:bg-red-700 disabled:opacity-50"
                >
                  {deleteMutation.isPending
                    ? <><Loader2 size={10} className="animate-spin" /> Deleting...</>
                    : <><Trash2 size={10} /> Delete permanently</>}
                </button>
              </div>
            </div>
          </td>
        </tr>
      )}
    </>
  )
}

// ─── page ────────────────────────────────────────────────────────────────────

export default function ArchivePage() {
  const navigate = useNavigate()

  const [selectedPortal, setSelectedPortal] = useState<string>('tender18')
  const [selectedState,  setSelectedState]  = useState<string>('all')
  const [selectedReason, setSelectedReason] = useState<string>('all')
  const [searchQuery,    setSearchQuery]    = useState<string>('')

  const { data: tenders = [], isLoading } = useArchiveTender18Tenders()

  const allStates = useMemo(() => {
    const set = new Set<string>()
    tenders.forEach(t => set.add(extractState(t.location)))
    return Array.from(set).sort()
  }, [tenders])

  const filtered = useMemo(() => {
    return tenders.filter(t => {
      if (selectedState !== 'all' && extractState(t.location) !== selectedState) return false
      if (selectedReason !== 'all' && t.archive_reason !== selectedReason) return false
      if (searchQuery) {
        const q = searchQuery.toLowerCase()
        const hit =
          (t.title?.toLowerCase().includes(q) ?? false) ||
          (t.reference_number?.toLowerCase().includes(q) ?? false) ||
          (t.organization?.toLowerCase().includes(q) ?? false)
        if (!hit) return false
      }
      return true
    })
  }, [tenders, selectedState, selectedReason, searchQuery])

  const activePortalConfig = PORTALS.find(p => p.id === selectedPortal)

  return (
    <div className="p-6 max-w-7xl mx-auto space-y-6">

      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <button
            onClick={() => navigate(-1)}
            className="p-2 rounded-lg text-slate-500 hover:text-slate-800 hover:bg-slate-100 transition-colors"
            title="Go back"
          >
            <ArrowLeft size={16} />
          </button>
          <div>
            <div className="flex items-center gap-2">
              <Archive size={18} className="text-slate-500" />
              <h1 className="text-xl font-semibold text-slate-900" style={lufgaSemiboldStyle}>
                Archived Tenders
              </h1>
            </div>
            <p className="text-xs text-slate-500 mt-0.5 ml-0.5" style={lufgaRegularStyle}>
              Tenders moved here when expired or manually deleted — never permanently lost.
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2 bg-slate-100 rounded-lg px-3 py-2">
          <Archive size={14} className="text-slate-500" />
          <span className="text-sm font-medium text-slate-700" style={lufgaSemiboldStyle}>
            {tenders.length} total archived
          </span>
        </div>
      </div>

      {/* Controls */}
      <div className="bg-white rounded-xl border border-slate-200 p-4">
        <div className="flex flex-wrap items-center gap-3">

          {/* Portal selector */}
          <div className="flex items-center gap-1.5">
            <Globe size={14} className="text-slate-400" />
            <span className="text-xs text-slate-500 font-medium" style={lufgaRegularStyle}>Portal:</span>
            <div className="relative">
              <select
                value={selectedPortal}
                onChange={e => setSelectedPortal(e.target.value)}
                className="text-xs border border-slate-200 rounded-lg pl-2 pr-7 py-1.5 focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white appearance-none cursor-pointer"
                style={lufgaRegularStyle}
              >
                {PORTALS.map(p => (
                  <option key={p.id} value={p.id} disabled={p.comingSoon}>
                    {p.name}{p.comingSoon ? ' (coming soon)' : ''}
                  </option>
                ))}
              </select>
              <ChevronDown size={11} className="absolute right-2 top-1/2 -translate-y-1/2 text-slate-400 pointer-events-none" />
            </div>
          </div>

          <div className="h-4 w-px bg-slate-200" />

          <div className="flex items-center gap-1.5">
            <Filter size={13} className="text-slate-400" />
            <span className="text-xs text-slate-500" style={lufgaRegularStyle}>Filters:</span>
          </div>

          {/* State filter */}
          <div className="flex items-center gap-1.5">
            <MapPin size={12} className="text-slate-400" />
            <span className="text-xs text-slate-400">State:</span>
            <div className="relative">
              <select
                value={selectedState}
                onChange={e => setSelectedState(e.target.value)}
                className="text-xs border border-slate-200 rounded-lg pl-2 pr-7 py-1.5 focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white appearance-none"
                style={lufgaRegularStyle}
              >
                <option value="all">All States</option>
                {allStates.map(s => (
                  <option key={s} value={s}>{s}</option>
                ))}
              </select>
              <ChevronDown size={11} className="absolute right-2 top-1/2 -translate-y-1/2 text-slate-400 pointer-events-none" />
            </div>
          </div>

          {/* Reason filter */}
          <div className="flex items-center gap-1.5">
            <span className="text-xs text-slate-400">Reason:</span>
            <div className="relative">
              <select
                value={selectedReason}
                onChange={e => setSelectedReason(e.target.value)}
                className="text-xs border border-slate-200 rounded-lg pl-2 pr-7 py-1.5 focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white appearance-none"
                style={lufgaRegularStyle}
              >
                <option value="all">All Reasons</option>
                <option value="expired">Expired</option>
                <option value="manual_delete">Manually Deleted</option>
                <option value="pipeline_cleanup">Auto-cleaned</option>
              </select>
              <ChevronDown size={11} className="absolute right-2 top-1/2 -translate-y-1/2 text-slate-400 pointer-events-none" />
            </div>
          </div>

          {/* Search */}
          <div className="relative flex-1 min-w-[200px]">
            <Search size={14} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-slate-400" />
            <input
              type="text"
              placeholder="Search title, ref, org..."
              value={searchQuery}
              onChange={e => setSearchQuery(e.target.value)}
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

          <span className="text-xs text-slate-400 ml-auto" style={lufgaRegularStyle}>
            {isLoading ? 'Loading...' : `${filtered.length} results`}
          </span>
        </div>
      </div>

      {/* Table */}
      <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
        {isLoading ? (
          <div className="flex flex-col items-center justify-center py-20 gap-3">
            <Loader2 size={28} className="text-blue-500 animate-spin" />
            <p className="text-sm text-slate-500" style={lufgaRegularStyle}>Loading archive…</p>
          </div>
        ) : filtered.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-20 gap-3">
            <Archive size={36} className="text-slate-200" />
            <p className="text-sm text-slate-500" style={lufgaRegularStyle}>
              {tenders.length === 0
                ? `No archived tenders for ${activePortalConfig?.name ?? selectedPortal} yet.`
                : 'No tenders match your filters.'}
            </p>
            {tenders.length > 0 && (
              <button
                onClick={() => { setSelectedState('all'); setSelectedReason('all'); setSearchQuery('') }}
                className="text-xs text-blue-600 hover:underline"
              >
                Clear filters
              </button>
            )}
          </div>
        ) : (
          <div className="overflow-x-auto relative">
            <table className="w-full text-left">
              <thead>
                <tr className="border-b border-slate-100 bg-slate-50">
                  <th className="px-4 py-3 text-[11px] font-semibold text-slate-500 uppercase tracking-wide">Tender</th>
                  <th className="px-4 py-3 text-[11px] font-semibold text-slate-500 uppercase tracking-wide">Organisation</th>
                  <th className="px-4 py-3 text-[11px] font-semibold text-slate-500 uppercase tracking-wide">State</th>
                  <th className="px-4 py-3 text-[11px] font-semibold text-slate-500 uppercase tracking-wide">Deadline</th>
                  <th className="px-4 py-3 text-[11px] font-semibold text-slate-500 uppercase tracking-wide">Value</th>
                  <th className="px-4 py-3 text-[11px] font-semibold text-slate-500 uppercase tracking-wide">Reason</th>
                  <th className="px-4 py-3 text-[11px] font-semibold text-slate-500 uppercase tracking-wide">Archived</th>
                  <th className="px-3 py-3 text-[11px] font-semibold text-slate-500 uppercase tracking-wide sticky right-0 bg-slate-50 border-l border-slate-100 shadow-[-4px_0_6px_-2px_rgba(0,0,0,0.04)]">Actions</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map(t => (
                  <ArchiveRow key={t.id} tender={t} />
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

    </div>
  )
}