"""
scraper/core/supabase_store.py
──────────────────────────────
All Supabase interactions for the scraper.
Uses service role key (full access — never exposed to frontend).

Operations:
  - create_run()                  start a scrape run record
  - fetch_all_seen_signatures()   one-time dedup snapshot (ref_no + url_hash set)
  - insert_tender()               write new tender row
  - finish_run()                  update run with final stats
"""

from __future__ import annotations
import os
import structlog
from datetime import datetime, timezone
from typing import Optional
from supabase import create_client, Client

from .schema import TenderRecord

log = structlog.get_logger()

# ─── Client (uses service key — server only) ─────────────────
def _get_client() -> Client:
    url = os.environ["SUPABASE_URL"]
    key = os.environ["SUPABASE_SERVICE_KEY"]   # NOT the anon key
    return create_client(url, key)


# ─── Run lifecycle ────────────────────────────────────────────
def create_run(sites_total: int) -> str:
    """
    Insert a new scrape_runs row.
    Returns the run UUID.
    """
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


# ─── One-time dedup snapshot ──────────────────────────────────
def fetch_all_seen_signatures() -> set[tuple[str, str]]:
    """
    Fetch every (reference_number, url_hash) pair from the tenders table
    in a single query at pipeline start.

    The pipeline stores this as an in-memory set and checks new tenders
    against it with O(1) lookups — no per-tender DB round-trips needed.
    Empty strings are used as fallback so each tuple is always hashable.
    """
    client = _get_client()
    res = (
        client.table("tenders")
        .select("reference_number, url_hash")
        .is_("deleted_at", None)
        .execute()
    )
    signatures = {
        (row.get("reference_number") or "", row.get("url_hash") or "")
        for row in (res.data or [])
    }
    log.info("signatures.loaded", count=len(signatures))
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


# ─── Archive expired tenders ───────────────────────────────
def archive_expired_eproc_tenders() -> int:
    """
    Triggers RPC shift_expired_eproc_tenders stored procedure to shift
    past-due tenders into archieve_eproc_tenders.
    """
    try:
        client = _get_client()
        res = client.rpc("shift_expired_eproc_tenders", {}).execute()
        count = res.data or 0
        log.info("eproc.archived_expired", count=count)
        return count
    except Exception as exc:
        log.warning("eproc.archive_expired_failed", error=str(exc))
        return 0