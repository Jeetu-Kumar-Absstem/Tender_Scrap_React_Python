// src/components/tenders/TenderCard.tsx
import { useState, useRef, useEffect } from 'react'
import { ExternalLink, Calendar, MapPin, Building2, Tag, FileDown, MoreVertical, CheckCircle2, Star, Trash2, AlertTriangle, X } from 'lucide-react'
import { format, parseISO, isAfter, startOfDay } from 'date-fns'
import type { Tender } from '../../types/tender'
import { clsx } from 'clsx'
import { useTenderActions } from '../../hooks/useTenderActions'

interface Props { tender: Tender }

const siteTypeBadge: Record<string, string> = {
  A: 'bg-amber-50 text-amber-700 border-amber-200',
  B: 'bg-blue-50  text-blue-700  border-blue-200',
  C: 'bg-teal-50  text-teal-700  border-teal-200',
  D: 'bg-gray-50  text-gray-500  border-gray-200',
}

const userStatusBadge: Record<string, string> = {
  active: 'bg-slate-50 text-slate-500 border-slate-200',
  done: 'bg-emerald-50 text-emerald-700 border-emerald-200',
  starred: 'bg-amber-50 text-amber-700 border-amber-200',
}

function openNicLink(url: string) {
  const isNic = url.includes('nicgep') || url.includes('nic.in') || url.includes('tenders.gov.in')
  if (!isNic) {
    window.open(url, '_blank', 'noopener,noreferrer')
    return
  }

  try {
    const parsed  = new URL(url)
    const baseUrl = `${parsed.protocol}//${parsed.hostname}/nicgep/app`

    // Open the portal homepage first to establish a fresh session cookie.
    // Can't read win.document (cross-origin CORS block), so we use a fixed
    // delay — 2500 ms is enough for NIC portals to complete session handshake.
    const win = window.open(baseUrl, '_blank')
    if (!win) {
      // Popup blocked — fall back to direct open
      window.open(url, '_blank', 'noopener,noreferrer')
      return
    }

    setTimeout(() => {
      try {
        win.location.href = url   // navigate same tab to the tender detail
      } catch {
        // Tab was closed by the user in the meantime — ignore
      }
    }, 2500)

  } catch {
    window.open(url, '_blank', 'noopener,noreferrer')
  }
}

function ActionMenu({ tender, onClose, onDeleteClick }: {
  tender: Tender
  onClose: () => void
  onDeleteClick: () => void
}) {
  const { setStatus } = useTenderActions()
  const menuRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) onClose()
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [onClose])

  const isDone    = tender.user_status === 'done'
  const isStarred = tender.user_status === 'starred'

  return (
    <div
      ref={menuRef}
      className="absolute right-0 top-7 z-50 bg-white rounded-lg shadow-lg border border-slate-200 py-1 w-44 text-sm"
    >
      <button
        onClick={() => {
          setStatus.mutate({ id: tender.id, user_status: isDone ? 'active' : 'done' })
          onClose()
        }}
        className="w-full flex items-center gap-2 px-3 py-2 hover:bg-slate-50 text-left text-slate-700"
      >
        <CheckCircle2 size={13} className={isDone ? 'text-emerald-500' : 'text-slate-400'} />
        {isDone ? 'Unmark Done' : 'Mark as Done'}
      </button>

      <button
        onClick={() => {
          setStatus.mutate({ id: tender.id, user_status: isStarred ? 'active' : 'starred' })
          onClose()
        }}
        className="w-full flex items-center gap-2 px-3 py-2 hover:bg-slate-50 text-left text-slate-700"
      >
        <Star size={13} className={isStarred ? 'text-amber-400 fill-amber-400' : 'text-slate-400'} />
        {isStarred ? 'Unstar' : 'Starred'}
      </button>

      <div className="border-t border-slate-100 my-1" />

      <button
        onClick={() => {
          onClose()
          onDeleteClick()
        }}
        className="w-full flex items-center gap-2 px-3 py-2 hover:bg-red-50 text-left text-red-600"
      >
        <Trash2 size={13} />
        Delete
      </button>
    </div>
  )
}

// Inline delete confirmation — replaces browser confirm()
function DeleteConfirm({ onConfirm, onCancel, loading }: {
  onConfirm: () => void
  onCancel: () => void
  loading: boolean
}) {
  return (
    <div className="mt-3 flex items-center justify-between gap-2 bg-red-50 border border-red-200 rounded-lg px-3 py-2">
      <div className="flex items-center gap-2 text-xs text-red-700">
        <AlertTriangle size={13} className="flex-shrink-0" />
        <span>Delete this tender permanently?</span>
      </div>
      <div className="flex items-center gap-1.5 flex-shrink-0">
        <button
          onClick={onCancel}
          className="flex items-center gap-1 text-xs px-2 py-1 rounded bg-white border border-slate-200 text-slate-600 hover:bg-slate-50"
        >
          <X size={10} /> Cancel
        </button>
        <button
          onClick={onConfirm}
          disabled={loading}
          className="flex items-center gap-1 text-xs px-2 py-1 rounded bg-red-600 text-white hover:bg-red-700 disabled:opacity-50"
        >
          <Trash2 size={10} />
          {loading ? 'Deleting...' : 'Delete'}
        </button>
      </div>
    </div>
  )
}

export default function TenderCard({ tender }: Props) {
  const [menuOpen, setMenuOpen]     = useState(false)
  const [showDelete, setShowDelete] = useState(false)
  const { deleteTender }            = useTenderActions()

  // Expired = deadline day is strictly before today; deadline on today is still active
  const deadlinePast = tender.deadline
    ? isAfter(startOfDay(new Date()), startOfDay(parseISO(tender.deadline)))
    : false

  const isDone    = tender.user_status === 'done'
  const isStarred = tender.user_status === 'starred'

  // Auto-delete from DB and hide expired tenders immediately
  useEffect(() => {
    if (deadlinePast) {
      deleteTender.mutate(tender.id)
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [deadlinePast, tender.id])

  if (deadlinePast) return null

  const handleConfirmDelete = () => {
    deleteTender.mutate(tender.id, {
      onSuccess: () => setShowDelete(false),
    })
  }

  return (
    <div className={clsx(
      'bg-white rounded-xl border p-4 transition-all relative',
      isDone    && 'opacity-60 border-slate-200',
      isStarred && 'border-amber-200 bg-amber-50/30',
      !isDone && !isStarred && 'border-slate-200 hover:border-blue-200 hover:shadow-sm',
    )}>

      {/* Top row: title + three-dot */}
      <div className="flex items-start justify-between gap-2">
        <div className="flex-1 min-w-0">
          <h3 className={clsx(
            'text-sm font-semibold leading-snug line-clamp-2',
            isDone ? 'line-through text-slate-400' : 'text-slate-900'
          )}>
            {tender.title ?? 'Untitled Tender'}
          </h3>

          <div className="flex items-center flex-wrap gap-1.5 mt-2">
            {tender.reference_number && (
              <span className="text-xs font-mono bg-slate-100 text-slate-600 px-2 py-0.5 rounded">
                {tender.reference_number.slice(0, 30)}
              </span>
            )}
            <span className={clsx('text-[11px] font-medium px-2 py-0.5 rounded border', siteTypeBadge[tender.site_type])}>
              Type {tender.site_type}
            </span>
            {tender.user_status !== 'active' && (
              <span className={clsx('text-[11px] font-medium px-2 py-0.5 rounded border', userStatusBadge[tender.user_status])}>
                {tender.user_status === 'done' ? 'Done' : 'Starred'}
              </span>
            )}
            <span className="text-[11px] text-slate-500 bg-slate-50 border border-slate-200 px-2 py-0.5 rounded">
              {tender.source_site}
            </span>
          </div>
        </div>

        {/* Three-dot menu */}
        <div className="relative flex-shrink-0">
          <button
            onClick={() => { setMenuOpen(v => !v); setShowDelete(false) }}
            className="p-1.5 rounded-lg text-slate-400 hover:text-slate-700 hover:bg-slate-100 transition-colors"
          >
            <MoreVertical size={15} />
          </button>
          {menuOpen && (
            <ActionMenu
              tender={tender}
              onClose={() => setMenuOpen(false)}
              onDeleteClick={() => setShowDelete(true)}
            />
          )}
        </div>
      </div>

      {/* Meta row */}
      <div className="flex items-center flex-wrap gap-3 mt-3 text-xs text-slate-500">
        {tender.organization && (
          <span className="flex items-center gap-1">
            <Building2 size={11} className="text-slate-400" />
            <span className="truncate max-w-[180px]">{tender.organization}</span>
          </span>
        )}
        {tender.location && (
          <span className="flex items-center gap-1">
            <MapPin size={11} className="text-slate-400" />
            {tender.location}
          </span>
        )}
        {tender.deadline && (
          <span className={clsx('flex items-center gap-1 font-medium',
            deadlinePast ? 'text-red-500' : 'text-emerald-600')}>
            <Calendar size={11} />
            {deadlinePast ? 'Expired ' : 'Due '}
            {format(parseISO(tender.deadline), 'dd MMM yyyy')}
          </span>
        )}
        {tender.estimated_value && (
          <span className="font-medium text-slate-700">₹{tender.estimated_value}</span>
        )}
      </div>

      {/* Keywords + open link */}
      <div className="flex items-center justify-between mt-3 pt-3 border-t border-slate-100">
        <div className="flex items-center gap-1 flex-wrap">
          <Tag size={11} className="text-slate-400" />
          {tender.keywords_matched.slice(0, 4).map(kw => (
            <span key={kw} className="text-[10px] bg-blue-50 text-blue-600 px-1.5 py-0.5 rounded font-medium uppercase tracking-wide">
              {kw}
            </span>
          ))}
        </div>
        <button
          onClick={() => openNicLink(tender.source_url)}
          className="flex items-center gap-1 text-[11px] text-blue-600 hover:text-blue-800 bg-blue-50 hover:bg-blue-100 px-2 py-1 rounded transition-colors"
        >
          <ExternalLink size={10} />
          Open
        </button>
      </div>

      {/* Doc links */}
      {tender.document_urls.length > 0 && (
        <div className="flex items-center gap-1 mt-2">
          {tender.document_urls.slice(0, 3).map((url, i) => (
            <a key={i} href={url} target="_blank" rel="noopener noreferrer"
              className="flex items-center gap-1 text-[11px] text-slate-500 hover:text-blue-600 bg-slate-50 hover:bg-blue-50 px-2 py-0.5 rounded border border-slate-200 transition-colors">
              <FileDown size={10} />
              Doc {i + 1}
            </a>
          ))}
        </div>
      )}

      {/* Inline delete confirmation */}
      {showDelete && (
        <DeleteConfirm
          onConfirm={handleConfirmDelete}
          onCancel={() => setShowDelete(false)}
          loading={deleteTender.isPending}
        />
      )}
    </div>
  )
}