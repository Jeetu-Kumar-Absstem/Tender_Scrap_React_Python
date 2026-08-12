-- ============================================================
-- Migration 005 — public.tenders table schema
-- ============================================================

create table if not exists public.tenders (
  id uuid not null default gen_random_uuid (),
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
  url_hash text not null,
  site_type text not null,
  keywords_matched text[] null default '{}'::text[],
  status text not null default 'PASS'::text,
  scraped_at timestamp with time zone not null default now(),
  deleted_at timestamp with time zone null,
  user_status text not null default 'active'::text,
  constraint tenders_pkey primary key (id),
  constraint unique_reference_number unique (reference_number),
  constraint unique_url_hash unique (url_hash),
  constraint tenders_run_id_fkey foreign KEY (run_id) references scrape_runs (id) on delete set null,
  constraint tenders_status_check check (
    (
      status = any (
        array['PASS'::text, 'REJECT'::text, 'ERROR'::text]
      )
    )
  ),
  constraint tenders_site_type_check check (
    (
      site_type = any (array['A'::text, 'B'::text, 'C'::text, 'D'::text])
    )
  ),
  constraint tenders_user_status_check check (
    (
      user_status = any (
        array['active'::text, 'done'::text, 'starred'::text]
      )
    )
  )
) TABLESPACE pg_default;

create index IF not exists idx_tenders_run_id on public.tenders using btree (run_id) TABLESPACE pg_default;
create index IF not exists idx_tenders_scraped_at on public.tenders using btree (scraped_at desc) TABLESPACE pg_default;
create index IF not exists idx_tenders_deadline on public.tenders using btree (deadline) TABLESPACE pg_default;
create index IF not exists idx_tenders_source_site on public.tenders using btree (source_site) TABLESPACE pg_default;
create index IF not exists idx_tenders_status on public.tenders using btree (status) TABLESPACE pg_default;
create index IF not exists idx_tenders_keywords on public.tenders using gin (keywords_matched) TABLESPACE pg_default;
create index IF not exists idx_tenders_deleted_at on public.tenders using btree (deleted_at) TABLESPACE pg_default where (deleted_at is null);
create index IF not exists idx_tenders_user_status on public.tenders using btree (user_status) TABLESPACE pg_default;
