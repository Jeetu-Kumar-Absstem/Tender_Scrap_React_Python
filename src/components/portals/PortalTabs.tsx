// src/components/portals/PortalTabs.tsx
import { clsx } from 'clsx'
import { Clock } from 'lucide-react'
import { PORTALS, PortalConfig } from '../../config/portals'

interface PortalTabsProps {
  activePortal: string
  onPortalChange: (portalId: string) => void
}

export default function PortalTabs({ activePortal, onPortalChange }: PortalTabsProps) {
  return (
    <div className="border-b border-slate-200">
      <nav className="flex gap-1 px-4 overflow-x-auto" aria-label="Portal tabs">
        {PORTALS.map((portal: PortalConfig) => {
          const isActive = activePortal === portal.id
          const isComingSoon = portal.comingSoon
          
          return (
            <button
              key={portal.id}
              onClick={() => !isComingSoon && onPortalChange(portal.id)}
              disabled={isComingSoon}
              className={clsx(
                'group relative flex items-center gap-2 px-4 py-3 text-sm font-medium transition-all whitespace-nowrap border-b-2',
                isActive
                  ? `border-${portal.color}-500 text-${portal.color}-600`
                  : 'border-transparent text-slate-500 hover:text-slate-700 hover:border-slate-300',
                isComingSoon && 'opacity-50 cursor-not-allowed hover:text-slate-500'
              )}
            >
              <portal.icon size={16} className={clsx(
                isActive && `text-${portal.color}-500`
              )} />
              <span>{portal.name}</span>
              {isComingSoon && (
                <span className="text-[10px] bg-slate-100 text-slate-500 px-1.5 py-0.5 rounded-full flex items-center gap-0.5">
                  <Clock size={10} />
                  Soon
                </span>
              )}
              {isActive && !isComingSoon && (
                <span className={`absolute bottom-0 left-0 right-0 h-0.5 bg-${portal.color}-500`} />
              )}
            </button>
          )
        })}
      </nav>
    </div>
  )
}