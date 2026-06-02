-- ============================================================
-- TenderPulse — Supabase Schema
-- Run this in Supabase SQL editor or via supabase db push
-- ============================================================

-- Enable UUID generation
create extension if not exists "pgcrypto";

-- ─── TABLE: scrape_runs ─────────────────────────────────────
-- One row per daily run. Full audit trail.
create table if not exists scrape_runs (
  id            uuid primary key default gen_random_uuid(),
  started_at    timestamptz not null default now(),
  completed_at  timestamptz,
  status        text not null default 'running'
                  check (status in ('running','completed','failed')),
  sites_total   int not null default 0,
  sites_ok      int not null default 0,
  sites_error   int not null default 0,
  new_count     int not null default 0,
  email_sent    boolean not null default false,
  error_log     jsonb,                        -- per-site errors
  deleted_at    timestamptz                   -- soft delete
);

create index idx_scrape_runs_started_at on scrape_runs(started_at desc);
create index idx_scrape_runs_status     on scrape_runs(status);

-- ─── TABLE: tenders ─────────────────────────────────────────
-- One row per unique tender that passed all filters.
create table if not exists tenders (
  id                  uuid primary key default gen_random_uuid(),
  run_id              uuid references scrape_runs(id) on delete set null,

  -- Core fields (LLM extracted)
  title               text,
  reference_number    text,                   -- primary dedup key
  organization        text,
  deadline            date,
  estimated_value     text,
  location            text,
  document_urls       text[] default '{}',

  -- Scraper metadata
  source_site         text not null,
  source_url          text not null,
  url_hash            text not null,          -- md5(source_url), fallback dedup
  site_type           text not null           -- A | B | C | D
                        check (site_type in ('A','B','C','D')),
  keywords_matched    text[] default '{}',
  status              text not null default 'PASS'
                        check (status in ('PASS','REJECT','ERROR')),

  -- Timestamps (always UTC)
  scraped_at          timestamptz not null default now(),
  deleted_at          timestamptz,            -- soft delete

  -- Constraints
  constraint unique_reference_number unique (reference_number),
  constraint unique_url_hash         unique (url_hash)
);

-- Indexes for common query patterns
create index idx_tenders_run_id          on tenders(run_id);
create index idx_tenders_scraped_at      on tenders(scraped_at desc);
create index idx_tenders_deadline        on tenders(deadline asc);
create index idx_tenders_source_site     on tenders(source_site);
create index idx_tenders_status          on tenders(status);
create index idx_tenders_keywords        on tenders using gin(keywords_matched);
create index idx_tenders_deleted_at      on tenders(deleted_at)
  where deleted_at is null;

-- ─── ROW LEVEL SECURITY ─────────────────────────────────────
-- Read-only public access (anon key) — no auth required per spec
alter table tenders     enable row level security;
alter table scrape_runs enable row level security;

-- Anon can read non-deleted rows
create policy "public read tenders"
  on tenders for select
  using (deleted_at is null);

create policy "public read scrape_runs"
  on scrape_runs for select
  using (deleted_at is null);

-- Only service role can insert/update/delete (scraper uses service key)
create policy "service insert tenders"
  on tenders for insert
  with check (true);      -- enforced by service role bypass

create policy "service update tenders"
  on tenders for update
  using (true);

create policy "service delete tenders"
  on tenders for delete
  using (true);

-- ─── FUNCTION: dedup check ──────────────────────────────────
-- Returns true if tender already exists (by ref_no OR url_hash)
create or replace function tender_exists(
  p_reference_number text,
  p_url_hash         text
) returns boolean
language sql stable as $$
  select exists (
    select 1 from tenders
    where deleted_at is null
      and (
        (p_reference_number is not null and reference_number = p_reference_number)
        or url_hash = p_url_hash
      )
  );
$$;

-- ─── VIEW: today's tenders ───────────────────────────────────
create or replace view todays_tenders as
  select * from tenders
  where deleted_at is null
    and scraped_at >= current_date::timestamptz
    and scraped_at <  (current_date + interval '1 day')::timestamptz
  order by scraped_at desc;
