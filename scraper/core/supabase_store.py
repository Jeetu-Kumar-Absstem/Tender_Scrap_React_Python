"""
scraper/core/supabase_store.py
──────────────────────────────
All Supabase interactions for the scraper.
Uses service role key (full access — never exposed to frontend).

Operations:
  - create_run()                  start a scrape run record
  - fetch_all_seen_signatures()   one-time dedup snapshot (ref_no + url_hash set)
                                  ↳ paginates ALL three sources in chunks of 1000:
                                      • tenders (active + soft-deleted)
                                      • archieve_eproc_tenders
  - insert_tender()               write new tender row
  - finish_run()                  update run with final stats
  - archive_expired_eproc_tenders() shift expired tenders to archive (pipeline only)
"""

from __future__ import annotations
import os
import structlog
from datetime import datetime, timezone
from typing import Optional
from supabase import create_client, Client

from .schema import TenderRecord

log = structlog.get_logger()

# Supabase default page size limit
_PAGE_SIZE = 1000


# ─── Client (uses service key — server only) ─────────────────
def _get_client() -> Client:
    url = os.environ["SUPABASE_URL"]
    key = os.environ["SUPABASE_SERVICE_KEY"]   # NOT the anon key
    return create_client(url, key)


# ─── Run lifecycle ────────────────────────────────────────────
def create_run(sites_total: int) -> str:
    """Insert a new scrape_runs row. Returns the run UUID."""
    client = _get_client()
    res = client.table("scrape_runs").insert({
        "status":      "running",
        "sites_total": sites_total,
        "sites_ok":    0,
        "sites_error": 0,
        "new_count":   0,
        "email_sent":  False,
    }).execute()

    run_id = res.data[0]["id"]
    log.info("run.created", run_id=run_id, sites_total=sites_total)
    return run_id


def finish_run(
    run_id:      str,
    sites_ok:    int,
    sites_error: int,
    new_count:   int,
    email_sent:  bool,
    error_log:   Optional[dict] = None,
    status:      str = "completed",
) -> None:
    client = _get_client()
    client.table("scrape_runs").update({
        "status":       status,
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "sites_ok":     sites_ok,
        "sites_error":  sites_error,
        "new_count":    new_count,
        "email_sent":   email_sent,
        "error_log":    error_log or {},
    }).eq("id", run_id).execute()

    log.info(
        "run.finished",
        run_id=run_id,
        status=status,
        new_count=new_count,
        email_sent=email_sent,
    )


# ─── Pagination helper ────────────────────────────────────────
def _paginate_all(client: Client, table: str, select: str) -> list[dict]:
    """
    Fetch ALL rows from a table by paginating in chunks of _PAGE_SIZE.
    Supabase silently truncates to 1000 rows without this — no warning,
    no error, just missing data.
    """
    all_rows: list[dict] = []
    offset = 0
    while True:
        res = (
            client.table(table)
            .select(select)
            .range(offset, offset + _PAGE_SIZE - 1)
            .execute()
        )
        rows = res.data or []
        all_rows.extend(rows)
        if len(rows) < _PAGE_SIZE:
            break       # reached the last page
        offset += _PAGE_SIZE
    return all_rows


# ─── One-time dedup snapshot ──────────────────────────────────
def fetch_all_seen_signatures() -> set[tuple[str, str]]:
    """
    Fetch every (reference_number, url_hash) pair we have EVER seen,
    from TWO sources, so the pipeline never re-inserts anything:

      1. tenders — ALL rows, including soft-deleted ones (no deleted_at filter).
         Edge case covered: if a tender was manually deleted before its deadline,
         it still has a row in this table (deleted_at IS NOT NULL). Without loading
         these rows the scraper would see it as new and re-insert it on the next run.

      2. archieve_eproc_tenders — tenders shifted here after deadline passed or
         manually archived. Without this, any tender that expired and was purged
         from `tenders` would look brand-new to the scraper.

    Both sets are merged into one in-memory set for O(1) dedup lookups.
    Each source is paginated in chunks of 1000 to bypass Supabase row limit.
    Empty strings used as fallback so every tuple is always hashable.
    """
    client = _get_client()

    def _to_sigs(rows: list[dict]) -> set[tuple[str, str]]:
        return {
            (row.get("reference_number") or "", row.get("url_hash") or "")
            for row in rows
        }

    # Source 1: tenders table — ALL rows (active + soft-deleted)
    # No .is_("deleted_at", None) filter — we intentionally include deleted rows
    # so manually-deleted tenders are still recognised as "already seen".
    tender_rows = _paginate_all(client, "tenders", "reference_number, url_hash")
    tender_sigs = _to_sigs(tender_rows)

    # Source 2: archive table — tenders moved here after expiry/manual archive
    archive_rows = _paginate_all(client, "archieve_eproc_tenders", "reference_number, url_hash")
    archive_sigs = _to_sigs(archive_rows)

    # Merge
    signatures = tender_sigs | archive_sigs

    log.info(
        "signatures.loaded",
        from_tenders=len(tender_sigs),
        from_archive=len(archive_sigs),
        total_unique=len(signatures),
    )
    print(
        f"[PIPELINE] Signatures loaded — "
        f"tenders (active+deleted): {len(tender_sigs)}, "
        f"archived: {len(archive_sigs)}, "
        f"total unique: {len(signatures)}"
    )
    return signatures


# ─── Insert tender ───────────────────────────────────────────
def insert_tender(record: TenderRecord) -> Optional[str]:
    """
    Insert one TenderRecord into the tenders table.
    Returns the inserted UUID, or None on error.
    Silently skips duplicates (unique constraint violation).
    """
    client = _get_client()

    try:
        res = client.table("tenders").insert(
            record.to_supabase_row()
        ).execute()
        tender_id = res.data[0]["id"]
        log.info(
            "tender.inserted",
            tender_id=tender_id,
            title=record.title,
            site=record.source_site,
        )
        return tender_id

    except Exception as exc:
        err = str(exc)
        if "unique" in err.lower() or "duplicate" in err.lower():
            log.debug("tender.duplicate_skipped", url=record.source_url)
        else:
            log.error("tender.insert_failed", error=err, url=record.source_url)
        return None


# ─── Archive expired tenders (called by pipeline only) ───────
def archive_expired_eproc_tenders() -> int:
    """
    Triggers RPC shift_expired_eproc_tenders stored procedure to shift
    past-due tenders into archieve_eproc_tenders.

    IMPORTANT: Must only be called from the Python pipeline (once per run,
    at the end of run_pipeline). NEVER call from the frontend — it caused
    repeated 409 conflicts because React Query was re-firing it on every
    component mount.
    """
    try:
        client = _get_client()
        res = client.rpc("shift_expired_eproc_tenders", {}).execute()
        count = res.data if isinstance(res.data, int) else 0
        log.info("eproc.archived_expired", count=count)
        print(f"[PIPELINE] Archived {count} expired tender(s) to archieve_eproc_tenders")
        return count
    except Exception as exc:
        log.warning("eproc.archive_expired_failed", error=str(exc))
        return 0