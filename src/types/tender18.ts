// src/types/tender18.ts
// Types for tender18_tenders table

import { UserStatus } from './tender'

export interface Tender18Tender {
  id: string
  title: string | null
  reference_number: string | null
  organization: string | null
  deadline: string | null
  estimated_value: string | null
  location: string | null
  source_url: string
  url_hash: string
  keywords_matched: string[]
  scraped_at: string
  deleted_at: string | null
  user_status: UserStatus
}

export interface Tender18Filters {
  search?: string
  keyword?: string
  location?: string
  user_status?: UserStatus | 'all'
  deadline_before?: string
  deadline_after?: string
}