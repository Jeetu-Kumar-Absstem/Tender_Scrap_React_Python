"""
scraper/core/supabase_store.py
──────────────────────────────
All Supabase interactions for the scraper.
Uses service role key (full access — never exposed to frontend).

Operations:
  - create_run()                  start a scrape run record
  - fetch_all_seen_signatures()   one-time dedup snapshot (ref_no + url_hash set)
                                  ↳ paginates tenders (active + soft-deleted) in chunks of 1000
  - insert_tender()               write new tender row
  - finish_run()                  update run with final stats
  - fetch_all_emailed_refs()      one-time email-dedup snapshot (ref_no + source_site set)
                                  ↳ paginates emailed_tenders in chunks of 1000
  - mark_tenders_emailed()        log emailed refs AFTER a successful digest send
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
    Fetch every (reference_number, url_hash) pair from the tenders table
    so the pipeline never re-inserts anything already seen.

    Includes ALL rows (active + soft-deleted) — no deleted_at filter.
    Edge case covered: if a tender was manually deleted before its deadline,
    it still has a row in this table (deleted_at IS NOT NULL). Without loading
    these rows the scraper would see it as new and re-insert it on the next run.

    Paginated in chunks of 1000 to bypass Supabase's silent row cap.
    Empty strings used as fallback so every tuple is always hashable.
    """
    client = _get_client()

    tender_rows = _paginate_all(client, "tenders", "reference_number, url_hash")
    signatures = {
        (row.get("reference_number") or "", row.get("url_hash") or "")
        for row in tender_rows
    }

    log.info("signatures.loaded", from_tenders=len(signatures))
    print(f"[PIPELINE] Signatures loaded — tenders (active+deleted): {len(signatures)}")
    return signatures


# ─── Email dedup snapshot ─────────────────────────────────────
def fetch_all_emailed_refs() -> set[tuple[str, str]]:
    """
    Fetch every (reference_number, source_site) pair from emailed_tenders.
    Called once at pipeline start, same pattern as fetch_all_seen_signatures().

    Purpose: prevent re-emailing a tender that was hard-deleted from the
    tenders table (so it no longer appears in seen_signatures) and then
    re-scraped and re-inserted on a subsequent run.

    Paginated in chunks of 1000 to bypass Supabase's silent row cap.
    """
    client = _get_client()

    rows = _paginate_all(client, "emailed_tenders", "reference_number, source_site")
    refs = {
        (row.get("reference_number") or "", row.get("source_site") or "")
        for row in rows
    }

    log.info("emailed_refs.loaded", count=len(refs))
    print(f"[PIPELINE] Emailed refs loaded — emailed_tenders: {len(refs)}")
    return refs


def mark_tenders_emailed(rows: list[dict], run_id: str) -> None:
    """
    Insert one row into emailed_tenders for every tender that was included
    in a successfully sent digest email.

    Called ONLY after send_digest() returns True — if the email fails,
    refs are NOT logged so the next run will retry sending them.

    Upsert with on_conflict so concurrent runs and retries are safe
    (duplicate upsert is a no-op — emailed_at is not overwritten).

    Skips tenders with no reference_number (rare edge case on some portals).
    """
    client = _get_client()

    records = []
    for r in rows:
        ref = (r.get("reference_number") or "").strip()
        if not ref:
            log.debug("mark_emailed.skipped_no_ref", url_hash=r.get("url_hash"), site=r.get("source_site"))
            continue
        records.append({
            "reference_number": ref,
            "url_hash":         r.get("url_hash", ""),
            "source_site":      r.get("source_site", ""),
            "run_id":           run_id,
        })

    if not records:
        log.info("mark_emailed.nothing_to_log")
        return

    client.table("emailed_tenders").upsert(
        records,
        on_conflict="reference_number,source_site",
    ).execute()

    log.info("mark_emailed.done", count=len(records))
    print(f"[EMAIL]  Logged {len(records)} ref(s) to emailed_tenders")


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