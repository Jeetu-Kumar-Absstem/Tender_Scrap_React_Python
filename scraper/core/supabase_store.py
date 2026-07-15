"""
scraper/core/supabase_store.py
──────────────────────────────
All Supabase interactions for the scraper.
Uses service role key (full access — never exposed to frontend).

Operations:
  - create_run()        start a scrape run record
  - tender_exists()     dedup check (ref_no + url_hash)
  - insert_tender()     write new tender row
  - finish_run()        update run with final stats
  - get_run_tenders()   fetch all tenders for a run (for email)
"""

from __future__ import annotations
import os
import structlog
from datetime import datetime, timezone
from typing import Optional
from supabase import create_client, Client

from .schema import TenderRecord, build_dedup_signature

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


# ─── Dedup check ─────────────────────────────────────────────
def tender_exists(
    reference_number: Optional[str],
    url_hash: str,
) -> bool:
    """
    Returns True if this tender is already in the database.
    Checks reference_number first (strongest), then url_hash.
    Uses the DB-side function for a single round trip.
    """
    client = _get_client()
    res = client.rpc("tender_exists", {
        "p_reference_number": reference_number,
        "p_url_hash":         url_hash,
    }).execute()
    return bool(res.data)


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


def _filter_existing_tenders(
    run_tenders: list[dict],
    existing_tenders: list[dict],
) -> list[dict]:
    """Exclude tenders whose reference or url hash already exists in the saved table."""
    existing_signatures = {
        build_dedup_signature(
            tender.get("reference_number"),
            tender.get("url_hash"),
        )
        for tender in existing_tenders
        if tender.get("reference_number") or tender.get("url_hash")
    }

    filtered: list[dict] = []
    for tender in run_tenders:
        signature = build_dedup_signature(
            tender.get("reference_number"),
            tender.get("url_hash"),
        )
        if signature in existing_signatures:
            continue
        filtered.append(tender)

    return filtered


# ─── Fetch tenders for a run (for email digest) ──────────────
def get_run_tenders(run_id: str) -> list[dict]:
    """Return PASS tenders from this run that are not already persisted in the tenders table for today."""
    client = _get_client()
    res = (
        client.table("tenders")
        .select("*")
        .eq("run_id", run_id)
        .eq("status", "PASS")
        .is_("deleted_at", None)
        .order("scraped_at", desc=False)
        .execute()
    )
    run_tenders = res.data or []

    existing_tenders: list[dict] = []
    try:
        existing_res = (
            client.table("todays_tenders")
            .select("reference_number,url_hash,run_id")
            .neq("run_id", run_id)
            .execute()
        )
        existing_tenders = existing_res.data or []
    except Exception:
        existing_res = (
            client.table("tenders")
            .select("reference_number,url_hash,run_id")
            .eq("status", "PASS")
            .is_("deleted_at", None)
            .neq("run_id", run_id)
            .execute()
        )
        existing_tenders = existing_res.data or []

    return _filter_existing_tenders(run_tenders, existing_tenders)
