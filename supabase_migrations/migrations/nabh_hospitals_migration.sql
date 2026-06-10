-- ============================================================
-- Migration: nabh_hospitals — v2 (address-only schema)
-- city + state are no longer stored as separate columns.
-- All city/state filtering happens in the UI by parsing address.
-- Cities for dropdown are fetched live from the NABH API.
-- ============================================================

-- Drop old table if migrating from v1
-- (comment out if you want to ALTER instead of recreate)
DROP TABLE IF EXISTS nabh_hospitals CASCADE;

CREATE TABLE nabh_hospitals (
    id               uuid DEFAULT gen_random_uuid() PRIMARY KEY,
    name             text NOT NULL,
    address          text,            -- full address: "..., City, State, 6-digit-PIN"
    phone            text,
    email            text,
    website          text,
    accreditation_no text,            -- unique dedup key (nullable for edge cases)
    scraped_at       timestamptz DEFAULT now(),
    updated_at       timestamptz DEFAULT now()
);

-- Unique index for upsert deduplication
CREATE UNIQUE INDEX nabh_hospitals_accno_unique
    ON nabh_hospitals (accreditation_no)
    WHERE accreditation_no IS NOT NULL;

-- Full-text search on name + address (city/state naturally included in address)
CREATE INDEX nabh_hospitals_fts ON nabh_hospitals
    USING gin(to_tsvector('english', coalesce(name,'') || ' ' || coalesce(address,'')));

-- Prefix search on name (fast ILIKE queries from the UI search box)
CREATE INDEX nabh_hospitals_name_trgm ON nabh_hospitals
    USING gin(name gin_trgm_ops);   -- requires pg_trgm extension

-- Enable trigram extension (safe to run repeatedly)
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- Auto-update updated_at
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS nabh_hospitals_updated_at ON nabh_hospitals;
CREATE TRIGGER nabh_hospitals_updated_at
    BEFORE UPDATE ON nabh_hospitals
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

-- Row Level Security
ALTER TABLE nabh_hospitals ENABLE ROW LEVEL SECURITY;

CREATE POLICY "allow_select_for_authenticated"
    ON nabh_hospitals FOR SELECT
    TO authenticated
    USING (true);

CREATE POLICY "service_role_all"
    ON nabh_hospitals FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- ── Migration note ────────────────────────────────────────────────────────────
-- If upgrading from v1 (which had city + state columns):
--   1. Run: ALTER TABLE nabh_hospitals DROP COLUMN IF EXISTS city, DROP COLUMN IF EXISTS state;
--   2. Re-run the scraper: python nabh_scraper.py
--   The address field already contains city+state in v1 data, so no data loss.
-- ─────────────────────────────────────────────────────────────────────────────