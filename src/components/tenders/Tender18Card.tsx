// src/components/tenders/Tender18Card.tsx
import { useState, useRef, useEffect } from 'react'
import { ExternalLink, Calendar, MapPin, Building2, Tag, MoreVertical, CheckCircle2, Star, Trash2, AlertTriangle, X, Loader2 } from 'lucide-react'
import { format, parseISO, isAfter, startOfDay } from 'date-fns'
import { clsx } from 'clsx'
import { useTender18Actions } from '../../hooks/useTender18'
import type { Tender18Tender } from '../../hooks/useTender18'

interface Props { tender: Tender18Tender }

function ActionMenu({ tender, onClose, onDeleteClick }: {
  tender: Tender18Tender
  onClose: () => void
  onDeleteClick: () => void
}) {
  const { updateStatus } = useTender18Actions()
  const menuRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        onClose()
      }
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [onClose])

  const isDone = tender.user_status === 'done'
  const isStarred = tender.user_status === 'starred'

  const handleStatusUpdate = (status: 'active' | 'done' | 'starred') => {
    updateStatus.mutate({ id: tender.id, user_status: status })
    onClose()
  }

  return (
    <div
      ref={menuRef}
      className="absolute right-0 top-7 z-50 bg-white rounded-lg shadow-lg border border-slate-200 py-1 w-44 text-sm"
    >
      <button
        onClick={() => handleStatusUpdate(isDone ? 'active' : 'done')}
        className="w-full flex items-center gap-2 px-3 py-2 hover:bg-slate-50 text-left text-slate-700"
      >
        <CheckCircle2 size={13} className={isDone ? 'text-emerald-500' : 'text-slate-400'} />
        {isDone ? 'Unmark Done' : 'Mark as Done'}
      </button>

      <button
        onClick={() => handleStatusUpdate(isStarred ? 'active' : 'starred')}
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
          {loading ? <Loader2 size={10} className="animate-spin" /> : <Trash2 size={10} />}
          {loading ? 'Deleting...' : 'Delete'}
        </button>
      </div>
    </div>
  )
}

export default function Tender18Card({ tender }: Props) {
  const [menuOpen, setMenuOpen] = useState(false)
  const [showDelete, setShowDelete] = useState(false)
  const { deleteTender } = useTender18Actions()

  const deadlinePast = tender.deadline
    ? isAfter(startOfDay(new Date()), startOfDay(parseISO(tender.deadline)))
    : false

  const isDone = tender.user_status === 'done'
  const isStarred = tender.user_status === 'starred'

  // Auto-delete expired tenders
  useEffect(() => {
    if (deadlinePast) {
      console.log('[Tender18Card] Auto-deleting expired tender:', tender.id)
      deleteTender.mutate(tender.id)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [deadlinePast, tender.id])

  // If expired, don't render
  if (deadlinePast) return null

  const handleConfirmDelete = () => {
    console.log('[Tender18Card] Confirming delete for tender:', tender.id)
    deleteTender.mutate(tender.id, {
      onSuccess: () => {
        console.log('[Tender18Card] Delete successful, closing confirmation')
        setShowDelete(false)
        setMenuOpen(false)
      },
      onError: (error) => {
        console.error('[Tender18Card] Delete failed:', error)
      },
    })
  }

  return (
    <div className={clsx(
      'bg-white rounded-xl border p-4 transition-all relative',
      isDone && 'opacity-60 border-slate-200',
      isStarred && 'border-amber-200 bg-amber-50/30',
      !isDone && !isStarred && 'border-slate-200 hover:border-blue-200 hover:shadow-sm',
    )}>
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
            <span className="text-[11px] font-medium px-2 py-0.5 rounded border bg-purple-50 text-purple-700 border-purple-200">
              Type D
            </span>
            <span className="text-[11px] text-slate-500 bg-slate-50 border border-slate-200 px-2 py-0.5 rounded">
              Tender18
            </span>
            {tender.user_status !== 'active' && (
              <span className={clsx(
                'text-[11px] font-medium px-2 py-0.5 rounded border',
                isDone ? 'bg-emerald-50 text-emerald-700 border-emerald-200' : 'bg-amber-50 text-amber-700 border-amber-200'
              )}>
                {isDone ? 'Done' : 'Starred'}
              </span>
            )}
          </div>
        </div>

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

      <div className="flex items-center justify-between mt-3 pt-3 border-t border-slate-100">
        <div className="flex items-center gap-1 flex-wrap">
          <Tag size={11} className="text-slate-400" />
          {(tender.keywords_matched || []).slice(0, 4).map((kw: string) => (
            <span key={kw} className="text-[10px] bg-blue-50 text-blue-600 px-1.5 py-0.5 rounded font-medium uppercase tracking-wide">
              {kw}
            </span>
          ))}
        </div>
        <button
          onClick={() => window.open(tender.source_url, '_blank', 'noopener,noreferrer')}
          className="flex items-center gap-1 text-[11px] text-blue-600 hover:text-blue-800 bg-blue-50 hover:bg-blue-100 px-2 py-1 rounded transition-colors"
        >
          <ExternalLink size={10} />
          Open
        </button>
      </div>

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