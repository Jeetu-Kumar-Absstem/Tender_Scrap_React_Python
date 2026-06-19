// src/components/portals/ComingSoonCard.tsx
import { Clock, Construction } from 'lucide-react'
import { PortalConfig } from '../../config/portals'

interface ComingSoonCardProps {
  portal: PortalConfig
}

export default function ComingSoonCard({ portal }: ComingSoonCardProps) {
  return (
    <div className="bg-white rounded-xl border border-slate-200 p-8 text-center">
      <div className="flex justify-center mb-4">
        <div className="w-16 h-16 bg-slate-100 rounded-full flex items-center justify-center">
          <Construction size={32} className="text-slate-400" />
        </div>
      </div>
      <h3 className="text-lg font-semibold text-slate-900 mb-2">
        {portal.name} Coming Soon
      </h3>
      <p className="text-sm text-slate-500 max-w-md mx-auto">
        We're working on integrating {portal.name} to bring you more tender opportunities.
        Stay tuned for updates!
      </p>
      <div className="mt-4 flex items-center justify-center gap-2 text-xs text-slate-400">
        <Clock size={14} />
        <span>Expected release: Q3 2024</span>
      </div>
    </div>
  )
}