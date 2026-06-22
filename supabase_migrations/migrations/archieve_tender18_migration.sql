-- Migration: Create archive_tender18_tenders table
-- Drop existing table first if needed, then run this fresh

CREATE TABLE archive_tender18_tenders (
  -- Core identity
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  original_id     uuid NOT NULL UNIQUE,    -- prevents duplicate archive rows

  -- Tender fields (mirrors tender18_tenders)
  title           text,
  reference_number text,
  organization    text,
  location        text,
  deadline        date,
  estimated_value text,
  source_url      text,
  keywords_matched text[],
  user_status     text DEFAULT 'active',
  scraped_at      timestamptz,

  -- Archive metadata
  archived_at     timestamptz NOT NULL DEFAULT now(),
  archive_reason  text NOT NULL           -- 'expired' | 'manual_delete' | 'pipeline_cleanup'
);

-- Indexes for fast lookups
CREATE INDEX idx_archive_tender18_archived_at
  ON archive_tender18_tenders (archived_at DESC);

CREATE INDEX idx_archive_tender18_reason
  ON archive_tender18_tenders (archive_reason);

-- Enable RLS
ALTER TABLE archive_tender18_tenders ENABLE ROW LEVEL SECURITY;

-- Allow all operations for authenticated users
CREATE POLICY "allow_all_authenticated" ON archive_tender18_tenders
  FOR ALL
  TO authenticated
  USING (true)
  WITH CHECK (true);