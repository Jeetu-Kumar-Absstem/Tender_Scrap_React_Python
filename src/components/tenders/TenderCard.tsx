// src/components/tenders/TenderCard.tsx
import { ExternalLink, Calendar, MapPin, Building2, Tag, FileDown } from 'lucide-react'
import { format, parseISO, isPast } from 'date-fns'
import type { Tender } from '../../types/tender'
import { clsx } from 'clsx'

interface Props { tender: Tender }

const siteTypeBadge: Record<string, string> = {
  A: 'bg-amber-50 text-amber-700 border-amber-200',
  B: 'bg-blue-50  text-blue-700  border-blue-200',
  C: 'bg-teal-50  text-teal-700  border-teal-200',
  D: 'bg-gray-50  text-gray-500  border-gray-200',
}

export default function TenderCard({ tender }: Props) {
  const deadlinePast = tender.deadline ? isPast(parseISO(tender.deadline)) : false

  return (
    <div className="bg-white rounded-xl border border-slate-200 p-4 hover:border-blue-200 hover:shadow-sm transition-all">
      <div className="flex items-start justify-between gap-3">
        <div className="flex-1 min-w-0">
          {/* Title + link */}
          <div className="flex items-start gap-2">
            <h3 className="text-sm font-semibold text-slate-900 leading-snug line-clamp-2 flex-1">
              {tender.title ?? 'Untitled Tender'}
            </h3>
            <a
              href={tender.source_url}
              target="_blank"
              rel="noopener noreferrer"
              className="flex-shrink-0 text-slate-400 hover:text-blue-600 mt-0.5"
            >
              <ExternalLink size={13} />
            </a>
          </div>

          {/* Ref + source badges */}
          <div className="flex items-center flex-wrap gap-1.5 mt-2">
            {tender.reference_number && (
              <span className="text-xs font-mono bg-slate-100 text-slate-600 px-2 py-0.5 rounded">
                {tender.reference_number}
              </span>
            )}
            <span className={clsx(
              'text-[11px] font-medium px-2 py-0.5 rounded border',
              siteTypeBadge[tender.site_type] ?? siteTypeBadge.A
            )}>
              Type {tender.site_type}
            </span>
            <span className="text-[11px] text-slate-500 bg-slate-50 border border-slate-200 px-2 py-0.5 rounded">
              {tender.source_site}
            </span>
          </div>
        </div>

        {/* Estimated value */}
        {tender.estimated_value && (
          <div className="text-right flex-shrink-0">
            <p className="text-[11px] text-slate-400">Est. Value</p>
            <p className="text-sm font-semibold text-slate-900">₹{tender.estimated_value}</p>
          </div>
        )}
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
          <span className={clsx(
            'flex items-center gap-1 font-medium',
            deadlinePast ? 'text-red-500' : 'text-emerald-600'
          )}>
            <Calendar size={11} />
            {deadlinePast ? 'Expired ' : 'Due '}
            {format(parseISO(tender.deadline), 'dd MMM yyyy')}
          </span>
        )}
      </div>

      {/* Keywords + docs */}
      <div className="flex items-center justify-between mt-3 pt-3 border-t border-slate-50">
        <div className="flex items-center gap-1 flex-wrap">
          <Tag size={11} className="text-slate-400" />
          {tender.keywords_matched.slice(0, 4).map(kw => (
            <span key={kw} className="text-[10px] bg-blue-50 text-blue-600 px-1.5 py-0.5 rounded font-medium uppercase tracking-wide">
              {kw}
            </span>
          ))}
        </div>
        {tender.document_urls.length > 0 && (
          <div className="flex items-center gap-1">
            {tender.document_urls.slice(0, 2).map((url, i) => (
              <a
                key={i}
                href={url}
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center gap-1 text-[11px] text-blue-600 hover:text-blue-800 bg-blue-50 px-2 py-0.5 rounded transition-colors"
              >
                <FileDown size={10} />
                Doc {i + 1}
              </a>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
