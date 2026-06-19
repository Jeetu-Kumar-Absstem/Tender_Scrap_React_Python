// src/config/portals.ts
import { Globe, Building2, FileSearch, Award } from 'lucide-react'

export interface PortalConfig {
  id: string
  name: string
  icon: any
  color: string
  description: string
  tableName: string
  enabled: boolean
  comingSoon: boolean
  scraperEndpoint: string
  statusEndpoint: string
}

export const PORTALS: PortalConfig[] = [
  {
    id: 'tender18',
    name: 'Tender18.com',
    icon: Globe,
    color: 'blue',
    description: 'PSA plant tenders from Tender18.com',
    tableName: 'tender18_tenders',
    enabled: true,
    comingSoon: false,
    scraperEndpoint: '/api/run-type-d',
    statusEndpoint: '/api/status-type-d',
  },
  {
    id: 'tendertiger',
    name: 'TenderTiger',
    icon: Building2,
    color: 'purple',
    description: 'Commercial tenders from TenderTiger',
    tableName: 'tendertiger_tenders',
    enabled: false,
    comingSoon: true,
    scraperEndpoint: '/api/run-tendertiger',
    statusEndpoint: '/api/status-tendertiger',
  },
  {
    id: 'bidassist',
    name: 'BidAssist',
    icon: Award,
    color: 'emerald',
    description: 'Government tenders from BidAssist',
    tableName: 'bidassist_tenders',
    enabled: false,
    comingSoon: true,
    scraperEndpoint: '/api/run-bidassist',
    statusEndpoint: '/api/status-bidassist',
  },
  {
    id: 'tenderdetail',
    name: 'TenderDetail',
    icon: FileSearch,
    color: 'amber',
    description: 'Detailed tenders from TenderDetail',
    tableName: 'tenderdetail_tenders',
    enabled: false,
    comingSoon: true,
    scraperEndpoint: '/api/run-tenderdetail',
    statusEndpoint: '/api/status-tenderdetail',
  },
]

export const getPortalById = (id: string): PortalConfig | undefined => {
  return PORTALS.find(p => p.id === id)
}

export const getEnabledPortals = (): PortalConfig[] => {
  return PORTALS.filter(p => p.enabled)
}

export const getActivePortals = (): PortalConfig[] => {
  return PORTALS.filter(p => p.enabled && !p.comingSoon)
}