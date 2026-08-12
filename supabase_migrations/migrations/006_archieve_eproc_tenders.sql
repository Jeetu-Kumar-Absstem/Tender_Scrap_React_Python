-- ============================================================
-- Migration 006 — public.archieve_eproc_tenders & automated shift
-- Run this script in the Supabase SQL Editor
-- ============================================================

-- 1. Create public.archieve_eproc_tenders table
create table if not exists public.archieve_eproc_tenders (
  id uuid not null default gen_random_uuid (),
  original_id uuid not null,
  run_id uuid null,
  title text null,
  reference_number text null,
  organization text null,
  deadline date null,
  estimated_value text null,
  location text null,
  document_urls text[] null default '{}'::text[],
  source_site text not null,
  source_url text not null,
  url_hash text null,
  site_type text not null,
  keywords_matched text[] null default '{}'::text[],
  status text null default 'PASS'::text,
  scraped_at timestamp with time zone null,
  user_status text null default 'active'::text,
  archived_at timestamp with time zone not null default now(),
  archive_reason text not null default 'expired'::text,
  constraint archieve_eproc_tenders_pkey primary key (id),
  constraint archieve_eproc_tenders_original_id_key unique (original_id),
  constraint archieve_eproc_tenders_archive_reason_check check (
    archive_reason = any (array['expired'::text, 'manual_delete'::text, 'pipeline_cleanup'::text])
  )
) TABLESPACE pg_default;

-- Create Indexes
create index IF not exists idx_archieve_eproc_tenders_original on public.archieve_eproc_tenders using btree (original_id) TABLESPACE pg_default;
create index IF not exists idx_archieve_eproc_tenders_archived_at on public.archieve_eproc_tenders using btree (archived_at desc) TABLESPACE pg_default;
create index IF not exists idx_archieve_eproc_tenders_source_site on public.archieve_eproc_tenders using btree (source_site) TABLESPACE pg_default;

-- Enable Row Level Security (RLS)
alter table public.archieve_eproc_tenders enable row level security;

-- Policies for public and authenticated access
drop policy if exists "public read archieve_eproc_tenders" on public.archieve_eproc_tenders;
create policy "public read archieve_eproc_tenders"
  on public.archieve_eproc_tenders for select
  using (true);

drop policy if exists "authenticated all archieve_eproc_tenders" on public.archieve_eproc_tenders;
create policy "authenticated all archieve_eproc_tenders"
  on public.archieve_eproc_tenders for all
  to authenticated
  using (true)
  with check (true);

-- Ensure public/authenticated update & delete policies exist on public.tenders
drop policy if exists "public update tenders" on public.tenders;
create policy "public update tenders"
  on public.tenders for update
  using (true);

drop policy if exists "public delete tenders" on public.tenders;
create policy "public delete tenders"
  on public.tenders for delete
  using (true);

-- 2. Stored Function: shift tenders whose due date has passed (today date > tenders due date)
create or replace function shift_expired_eproc_tenders()
returns int
language plpgsql as $$
declare
  shifted_count int := 0;
begin
  -- Copy tenders where deadline < current_date to archieve_eproc_tenders
  insert into public.archieve_eproc_tenders (
    original_id, run_id, title, reference_number, organization, deadline,
    estimated_value, location, document_urls, source_site, source_url,
    url_hash, site_type, keywords_matched, status, scraped_at, user_status,
    archived_at, archive_reason
  )
  select
    id, run_id, title, reference_number, organization, deadline,
    estimated_value, location, document_urls, source_site, source_url,
    url_hash, site_type, keywords_matched, status, scraped_at, user_status,
    now(), 'expired'
  from public.tenders
  where deleted_at is null
    and deadline is not null
    and deadline < current_date
  on conflict (original_id) do nothing;

  -- Soft-delete moved tenders from public.tenders table
  update public.tenders
    set deleted_at = now()
  where deleted_at is null
    and deadline is not null
    and deadline < current_date;

  get diagnostics shifted_count = row_count;
  return shifted_count;
end;
$$;
