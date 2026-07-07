// src/types/gemTender.ts

export interface GemTender {
  id: string
  title: string | null
  reference_number: string | null
  organization: string | null
  location: string | null
  deadline: string | null
  estimated_value: string | null
  source_url: string
  url_hash: string
  keywords_matched: string[]
  user_status: 'active' | 'done' | 'starred'
  scraped_at: string
  created_at: string
  updated_at: string
  deleted_at: string | null
}