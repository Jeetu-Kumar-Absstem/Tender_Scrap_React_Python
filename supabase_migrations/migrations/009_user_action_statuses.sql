-- ============================================================
-- Migration 009 — expand tender user action statuses
-- ============================================================

update public.tenders
  set user_status = 'applied'
where user_status = 'done';

update public.gem_tenders
  set user_status = 'applied'
where user_status = 'done';

update public.today_gem_tenders
  set user_status = 'applied'
where user_status = 'done';

update public.archieve_eproc_tenders
  set user_status = 'applied'
where user_status = 'done';

update public.archive_gem_tenders
  set user_status = 'applied'
where user_status = 'done';

alter table if exists public.tenders
  drop constraint if exists tenders_user_status_check;

alter table if exists public.tenders
  add constraint tenders_user_status_check
  check (user_status in ('active', 'applied', 'expired', 'not_in_scope', 'not_qualified', 'starred'));

alter table if exists public.gem_tenders
  drop constraint if exists gem_tenders_user_status_check;

alter table if exists public.gem_tenders
  add constraint gem_tenders_user_status_check
  check (user_status in ('active', 'applied', 'expired', 'not_in_scope', 'not_qualified', 'starred'));

alter table if exists public.today_gem_tenders
  drop constraint if exists today_gem_tenders_user_status_check;

alter table if exists public.today_gem_tenders
  add constraint today_gem_tenders_user_status_check
  check (user_status in ('active', 'applied', 'expired', 'not_in_scope', 'not_qualified', 'starred'));
