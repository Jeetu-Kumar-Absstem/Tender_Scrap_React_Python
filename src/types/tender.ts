// src/types/tender.ts
// Single source of truth — matches Supabase schema exactly

export type SiteType = 'A' | 'B' | 'C' | 'D'
export type TenderStatus = 'PASS' | 'REJECT' | 'ERROR'
export type RunStatus = 'running' | 'completed' | 'failed'

// ─── Core tender record (mirrors DB row) ────────────────────
export interface Tender {
  id: string
  run_id: string | null
  title: string | null
  reference_number: string | null
  organization: string | null
  deadline: string | null           // ISO date string YYYY-MM-DD
  estimated_value: string | null
  location: string | null
  document_urls: string[]
  source_site: string
  source_url: string
  url_hash: string
  site_type: SiteType
  keywords_matched: string[]
  status: TenderStatus
  scraped_at: string                // ISO timestamptz
  deleted_at: string | null
}

// ─── Scrape run record ───────────────────────────────────────
export interface ScrapeRun {
  id: string
  started_at: string
  completed_at: string | null
  status: RunStatus
  sites_total: number
  sites_ok: number
  sites_error: number
  new_count: number
  email_sent: boolean
  error_log: Record<string, string> | null
  deleted_at: string | null
}

// ─── API response wrapper ────────────────────────────────────
export interface ApiResponse<T> {
  success: boolean
  data: T | null
  error: string | null
  meta?: {
    total?: number
    page?: number
    limit?: number
    has_more?: boolean
  }
}

// ─── Filter params for tender list ──────────────────────────
export interface TenderFilters {
  search?: string
  source_site?: string
  site_type?: SiteType
  keyword?: string
  deadline_before?: string
  deadline_after?: string
  date_from?: string
  date_to?: string
  page?: number
  limit?: number
}

// ─── Dashboard stats ─────────────────────────────────────────
export interface DashboardStats {
  total_tenders: number
  new_today: number
  sites_monitored: number
  last_run_at: string | null
  last_run_status: RunStatus | null
  tenders_by_site: { site: string; count: number }[]
  tenders_by_keyword: { keyword: string; count: number }[]
}
