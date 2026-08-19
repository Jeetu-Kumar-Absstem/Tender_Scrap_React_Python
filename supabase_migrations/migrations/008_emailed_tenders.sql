-- ============================================================
-- Migration: 008_emailed_tenders.sql
-- Purpose  : Append-only email-dedup log for Type B tenders.
--
-- Problem solved:
--   A user marks a tender "done" or it gets soft-deleted
--   (deleted_at set) before its deadline. Next scraper run
--   re-scrapes it, insert_tender() succeeds (new uuid, same
--   ref/url_hash hits the UNIQUE constraint so it either
--   re-inserts or upserts), and the email fires again.
--
-- Solution:
--   After a digest email is sent, record every
--   (reference_number, url_hash, source_site) that was
--   included. On the next run, filter those out before
--   sending the email, regardless of what happened in
--   the tenders table.
--
-- Scope: Type B only in practice (pipeline.py only calls
--        this for site_type = 'B'), but the table is
--        site_type-agnostic so you can extend later.
-- ============================================================

CREATE TABLE IF NOT EXISTS public.emailed_tenders (
    id               bigserial        PRIMARY KEY,

    -- Primary dedup key: reference_number from tenders table.
    -- NIC portals always have one. Stored normalised (trimmed).
    reference_number text             NOT NULL,

    -- Secondary dedup key: md5(source_url), matches tenders.url_hash.
    -- Lets us dedup even if two portals share a ref number string.
    url_hash         text             NOT NULL,

    -- Which portal — matches tenders.source_site exactly.
    -- e.g. "Delhi", "Haryana", "eProcure / CPPP"
    source_site      text             NOT NULL,

    -- Scrape run that triggered the email (for audit / debugging).
    run_id           uuid             NULL
        REFERENCES public.scrape_runs (id) ON DELETE SET NULL,

    -- When the digest was successfully sent.
    emailed_at       timestamptz      NOT NULL DEFAULT now()
);

-- ── Dedup constraint ──────────────────────────────────────────────────────────
-- (reference_number, source_site) is the fast in-memory check.
-- url_hash is the tiebreaker for portals that reuse ref numbers.
-- We make the UNIQUE on (reference_number, source_site) because that is
-- what the pipeline loads into the set — url_hash is stored for auditing.
CREATE UNIQUE INDEX IF NOT EXISTS emailed_tenders_ref_site_uidx
    ON public.emailed_tenders (reference_number, source_site);

-- ── Lookup index ──────────────────────────────────────────────────────────────
-- Used by fetch_all_emailed_refs() which SELECTs only these two columns.
CREATE INDEX IF NOT EXISTS emailed_tenders_ref_idx
    ON public.emailed_tenders (reference_number);

-- ── RLS ───────────────────────────────────────────────────────────────────────
-- Service-role key (used by scraper) bypasses RLS by default in Supabase.
-- Anon / authenticated roles cannot touch this table.
ALTER TABLE public.emailed_tenders ENABLE ROW LEVEL SECURITY;

-- ── Comments ──────────────────────────────────────────────────────────────────
COMMENT ON TABLE public.emailed_tenders IS
    'Append-only log of tenders included in digest emails. '
    'Prevents re-emailing when a tender is soft-deleted and re-scraped. '
    'Never DELETE rows from this table.';

COMMENT ON COLUMN public.emailed_tenders.reference_number IS
    'Matches tenders.reference_number (trimmed). Primary dedup key.';

COMMENT ON COLUMN public.emailed_tenders.url_hash IS
    'Matches tenders.url_hash = md5(source_url). Secondary dedup / audit.';

COMMENT ON COLUMN public.emailed_tenders.source_site IS
    'Matches tenders.source_site exactly — e.g. "Delhi", "Haryana".';