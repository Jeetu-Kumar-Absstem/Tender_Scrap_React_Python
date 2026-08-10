create table public.archive_gem_tenders (
  id uuid not null default gen_random_uuid (),
  original_id uuid not null,
  title text null,
  reference_number text null,
  organization text null,
  location text null,
  deadline text null,
  estimated_value text null,
  source_url text null,
  keywords_matched text[] null default '{}'::text[],
  user_status text null default 'active'::text,
  scraped_at timestamp with time zone null,
  archived_at timestamp with time zone null default now(),
  archive_reason text not null,
  matched_category text null,
  constraint archive_gem_tenders_pkey primary key (id),
  constraint archive_gem_tenders_archive_reason_check check (
    (
      archive_reason = any (
        array[
          'expired'::text,
          'manual_delete'::text,
          'pipeline_cleanup'::text
        ]
      )
    )
  )
) TABLESPACE pg_default;

create index IF not exists idx_archive_gem_tenders_original on public.archive_gem_tenders using btree (original_id) TABLESPACE pg_default;

create index IF not exists idx_archive_gem_tenders_archived_at on public.archive_gem_tenders using btree (archived_at) TABLESPACE pg_default;

create index IF not exists idx_archive_gem_tenders_matched_category on public.archive_gem_tenders using btree (matched_category) TABLESPACE pg_default;