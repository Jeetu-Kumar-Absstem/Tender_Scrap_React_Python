-- ============================================================
-- Migration 007 — Public RLS policies for GeM tables
-- Run this script in the Supabase SQL Editor
-- ============================================================

-- Enable RLS on all GeM tables
alter table if exists public.gem_tenders enable row level security;
alter table if exists public.today_gem_tenders enable row level security;
alter table if exists public.archive_gem_tenders enable row level security;

-- Policies for public / anon access on gem_tenders
drop policy if exists "public_all_gem_tenders" on public.gem_tenders;
create policy "public_all_gem_tenders" on public.gem_tenders
  for all using (true) with check (true);

-- Policies for public / anon access on today_gem_tenders
drop policy if exists "public_all_today_gem_tenders" on public.today_gem_tenders;
create policy "public_all_today_gem_tenders" on public.today_gem_tenders
  for all using (true) with check (true);

-- Policies for public / anon access on archive_gem_tenders
drop policy if exists "public_all_archive_gem_tenders" on public.archive_gem_tenders;
create policy "public_all_archive_gem_tenders" on public.archive_gem_tenders
  for all using (true) with check (true);
