-- ============================================================
-- Migration 002 — user_status column + expired tender cleanup
-- Run this in Supabase SQL Editor
-- ============================================================

-- Add user_status to tenders table
alter table tenders
  add column if not exists user_status text
    check (user_status in ('active', 'done', 'starred'))
    default 'active' not null;

create index if not exists idx_tenders_user_status on tenders(user_status);

-- Function: soft-delete tenders past their deadline
create or replace function cleanup_expired_tenders()
returns int
language plpgsql as $$
declare
  deleted_count int;
begin
  update tenders
    set deleted_at = now()
  where deleted_at is null
    and deadline is not null
    and deadline < current_date;

  get diagnostics deleted_count = row_count;
  return deleted_count;
end;
$$;

-- Update RLS policy to include user_status filter support
drop policy if exists "public read tenders" on tenders;
create policy "public read tenders"
  on tenders for select
  using (deleted_at is null);

drop policy if exists "service delete tenders" on tenders;
create policy "service delete tenders"
  on tenders for delete
  using (true);
