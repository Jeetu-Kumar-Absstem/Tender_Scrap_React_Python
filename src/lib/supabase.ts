// src/lib/supabase.ts
import { createClient } from '@supabase/supabase-js'
import type { Tender, ScrapeRun } from '../types/tender'

const supabaseUrl = import.meta.env.VITE_SUPABASE_URL
const supabaseAnonKey = import.meta.env.VITE_SUPABASE_ANON_KEY

if (!supabaseUrl || !supabaseAnonKey) {
  throw new Error('Missing VITE_SUPABASE_URL or VITE_SUPABASE_ANON_KEY in .env')
}

// Typed DB interface — keeps queries type-safe
export interface Database {
  public: {
    Tables: {
      tenders: {
        Row: Tender
        Insert: Omit<Tender, 'id' | 'scraped_at' | 'deleted_at'>
        Update: Partial<Tender>
      }
      scrape_runs: {
        Row: ScrapeRun
        Insert: Omit<ScrapeRun, 'id' | 'started_at' | 'deleted_at'>
        Update: Partial<ScrapeRun>
      }
    }
    Views: {
      todays_tenders: { Row: Tender }
    }
  }
}

export const supabase = createClient<Database>(supabaseUrl, supabaseAnonKey, {
  auth: { persistSession: true },   
})
