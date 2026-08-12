"""
scraper/pipeline.py
Daily orchestrator for Type B plus HLL Lifecare plus GeM BidPlus.

Flow:
  1. Create scrape_run record in Supabase
  2. Load ALL existing tender signatures into memory (one-time dedup snapshot)
  3. Launch ONE shared browser
  4. Run Type B sites concurrently, HLL Lifecare via Type A, and GeM BidPlus via Type C
  5. Dedup check -> if new: insert to DB immediately + add to in-memory new_tender_rows
  6. End of run (normal OR Ctrl+C OR crash): if any new_tender_rows -> send Brevo email digest
  7. Update scrape_run with final stats
  8. Close shared browser

Email guarantee:
  - new_tender_rows is built in-memory as tenders are inserted during the run
  - Email fires in a `finally` block so it always runs:
      normal completion  -> email sent
      Ctrl+C / SIGINT    -> email sent
      unexpected crash   -> email sent
  - No extra DB round-trip needed for email -- we use the in-memory list
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys
from typing import Optional

import structlog
from playwright.async_api import async_playwright, Browser

from .core.schema import SITES_BY_TYPE, SiteType, SiteConfig
from .core.supabase_store import create_run, finish_run, fetch_all_seen_signatures, insert_tender
from .email.brevo import send_digest
from .scrapers.type_a import scrape_type_a
from .scrapers.type_b import scrape_type_b

structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.add_log_level,
        structlog.processors.JSONRenderer(),
    ],
    wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
)
log = structlog.get_logger()

# Max sites scraped simultaneously.
# 5 is a safe default: low memory pressure, good parallelism.
# Raise to 8-10 if your machine has >16 GB RAM and you want more speed.
CONCURRENCY = 7


# Asyncio lock to serialize Supabase writes (not thread-safe)
_db_lock = asyncio.Lock()


async def _scrape_site(
    site: SiteConfig,
    run_id: str,
    browser: Browser,
    sem: asyncio.Semaphore,
    stats: dict,
    new_tender_rows: list,          # shared list -- append new tender dicts here
    seen_signatures: set,           # in-memory dedup set loaded once at pipeline start
) -> tuple[SiteConfig, int, Optional[str]]:
    """
    Scrape one site under the semaphore.
    Inserts new tenders into DB immediately as site completes.
    Appends newly-inserted tender dicts to `new_tender_rows` for the email digest.
    Returns (site, new_count, error_message_or_None).
    """
    async with sem:
        print(f"\n[SCRAPER] >>  Starting  : {site.name}  (type={site.site_type.value})")
        log.info("site.start", site=site.name, type=site.site_type.value)
        try:
            if site.site_type == SiteType.B:
                records = await scrape_type_b(site, run_id=run_id, browser=browser)
            elif site.site_type == SiteType.A and site.name == "HLL Lifecare":
                records = await asyncio.to_thread(scrape_type_a, site, run_id)
            else:
                print(f"[SCRAPER] --  Skipped   : {site.name}  (not in active scope)")
                log.info("site.skipped", site=site.name, type=site.site_type.value)
                return site, 0, None

            print(f"[SCRAPER] ~~ Scraped   : {site.name}  -> {len(records)} candidate record(s)")

            # -- Dedup + insert (serialised so Supabase writes don't race) --
            new_count = 0
            async with _db_lock:
                for record in records:
                    if record is None or record.status != "PASS":
                        continue

                    # In-memory dedup check (set loaded once at pipeline start)
                    sig = (record.reference_number or "", record.url_hash or "")

                    if sig in seen_signatures:
                        # Already in DB -- skip
                        print(
                            f"[DEDUP]   == Duplicate  : [{site.name}] "
                            f"ref={record.reference_number or 'N/A'}  "
                            f'title="{(record.title or "")[:60]}"'
                        )
                        log.debug(
                            "tender.duplicate",
                            site=site.name,
                            ref=record.reference_number,
                            url_hash=record.url_hash,
                        )
                        continue

                    # Brand-new tender -- insert to DB immediately,
                    # mark seen so concurrent sites don't re-insert,
                    # and add to new_tender_rows for the email digest.
                    inserted_id = insert_tender(record)
                    if inserted_id:
                        seen_signatures.add(sig)
                        new_count += 1
                        stats["new_count"] += 1

                        # Build the dict the email renderer expects and keep it
                        row = record.to_supabase_row()
                        row["id"] = inserted_id
                        new_tender_rows.append(row)

                        print(
                            f"[NEW]     OK Inserted   : [{site.name}] "
                            f"id={inserted_id}  "
                            f"ref={record.reference_number or 'N/A'}  "
                            f'title="{(record.title or "")[:60]}"'
                        )
                        log.info(
                            "tender.new",
                            id=inserted_id,
                            title=record.title,
                            site=site.name,
                            ref=record.reference_number,
                        )

            print(f"[SCRAPER] OK  Done      : {site.name}  -- {new_count} new / {len(records)} total")
            log.info("site.done", site=site.name, records=len(records), new=new_count)
            return site, new_count, None

        except Exception as exc:
            print(f"[SCRAPER] !! Failed    : {site.name}  -- {exc}")
            log.error("site.failed", site=site.name, error=str(exc))
            return site, 0, str(exc)


def _send_email_digest(new_tender_rows: list, run_id: str) -> bool:
    """
    Send email digest if there are new tenders.
    Called from the finally block so it fires on normal completion,
    Ctrl+C, or any unexpected crash.
    Returns True if email was sent successfully.
    """
    if not new_tender_rows:
        print("[EMAIL]  ii  No new tenders -- digest skipped")
        log.info("pipeline.no_new_tenders")
        return False

    print(f"[EMAIL]  Sending digest for {len(new_tender_rows)} new tender(s) ...")
    try:
        email_sent = send_digest(new_tender_rows, run_id=run_id)
        if email_sent:
            print("[EMAIL]  OK Digest sent successfully")
        else:
            print("[EMAIL]  !! Digest send failed (check BREVO_* env vars / logs)")
        return email_sent
    except Exception as exc:
        print(f"[EMAIL]  !! Digest send raised exception: {exc}")
        log.error("email.exception", error=str(exc))
        return False


async def run_pipeline() -> None:
    sites = (
         [s for s in SITES_BY_TYPE[SiteType.A] if s.name == "HLL Lifecare"]
        +SITES_BY_TYPE[SiteType.B]
    )
    log.info("pipeline.start", sites=len(sites), concurrency=CONCURRENCY)

    run_id = create_run(sites_total=len(sites))

    stats = {
        "sites_ok": 0,
        "sites_error": 0,
        "new_count": 0,
        "errors": {},
    }

    # -- One-time DB fetch: all existing (ref, url_hash) pairs into a set ------
    # Single query replaces per-tender tender_exists() DB calls.
    # Any tender already in DB will be skipped during this run.
    seen_signatures: set[tuple[str, str]] = fetch_all_seen_signatures()
    print(f"[PIPELINE] Loaded {len(seen_signatures)} existing tender signature(s) from DB")
    log.info("pipeline.signatures_loaded", count=len(seen_signatures))

    # Accumulates dicts for every newly-inserted tender this run.
    # Used for the email digest -- no extra DB fetch needed.
    # Populated inside _scrape_site as each tender is inserted.
    new_tender_rows: list[dict] = []

    # results placeholder so finally block can reference it safely
    results = []
    email_sent = False
    interrupted = False

    try:
        async with async_playwright() as pw:
            # -- Launch ONE shared browser for all sites --------------
            browser = await pw.chromium.launch(
                headless=True,
                args=[
                    "--no-sandbox",
                    "--disable-blink-features=AutomationControlled",
                    "--disable-dev-shm-usage",
                    "--disable-gpu",
                    "--disable-web-security",
                    "--disable-features=IsolateOrigins,site-per-process",
                    "--allow-running-insecure-content",
                    "--disable-site-isolation-trials",
                    "--no-first-run",
                    "--no-default-browser-check",
                    "--disable-infobars",
                    "--window-size=1920,1080",
                    "--start-maximized",
                ],
            )
            log.info("pipeline.browser_launched")

            try:
                sem = asyncio.Semaphore(CONCURRENCY)

                # -- Fire all sites concurrently, capped by semaphore -
                tasks = [
                    _scrape_site(site, run_id, browser, sem, stats, new_tender_rows, seen_signatures)
                    for site in sites
                ]
                results = await asyncio.gather(*tasks, return_exceptions=False)

            finally:
                await browser.close()
                log.info("pipeline.browser_closed")

        # -- Tally results (inserts already done inside _scrape_site) -
        for site, new_count, error in results:
            if error:
                stats["sites_error"] += 1
                stats["errors"][site.name] = error
            else:
                stats["sites_ok"] += 1

        # -- Console summary ------------------------------------------
        print("\n" + "=" * 60)
        print(f"[PIPELINE] Run complete  run_id={run_id}")
        print(f"[PIPELINE] Sites OK      : {stats['sites_ok']}")
        print(f"[PIPELINE] Sites failed  : {stats['sites_error']}")
        print(f"[PIPELINE] New tenders   : {stats['new_count']}")
        if stats["errors"]:
            for site_name, err in stats["errors"].items():
                print(f"[PIPELINE]   **  {site_name}: {err}")
        print("=" * 60 + "\n")

    except (KeyboardInterrupt, asyncio.CancelledError):
        interrupted = True
        print("\n[PIPELINE] !! Interrupted by user (Ctrl+C / stop signal)")
        print(f"[PIPELINE]    Collected {len(new_tender_rows)} new tender(s) before stop")
        log.warning("pipeline.interrupted", new_so_far=len(new_tender_rows))

    except Exception as exc:
        interrupted = True
        print(f"\n[PIPELINE] !! Crashed unexpectedly: {exc}")
        print(f"[PIPELINE]    Collected {len(new_tender_rows)} new tender(s) before crash")
        log.error("pipeline.crashed", error=str(exc), new_so_far=len(new_tender_rows))

    finally:
        # -- Email digest ------------------------------------------------
        # Fires in ALL cases: normal completion, Ctrl+C, or crash.
        # new_tender_rows holds every tender inserted THIS run in-memory.
        # No extra DB round-trip needed.
        if interrupted:
            print("[EMAIL]  Pipeline was interrupted -- sending partial digest if any tenders found ...")

        email_sent = _send_email_digest(new_tender_rows, run_id=run_id)

        # -- Finalise run ------------------------------------------------
        finish_run(
            run_id=run_id,
            sites_ok=stats["sites_ok"],
            sites_error=stats["sites_error"],
            new_count=stats["new_count"],
            email_sent=email_sent,
            error_log=stats["errors"] or None,
            status="interrupted" if interrupted else (
                "failed" if stats["sites_error"] == len(sites) else "completed"
            ),
        )

        log.info(
            "pipeline.done",
            new=stats["new_count"],
            ok=stats["sites_ok"],
            errors=stats["sites_error"],
            email_sent=email_sent,
            interrupted=interrupted,
        )


def main() -> None:
    import io
    # Force UTF-8 on Windows -- cp1252 terminal can't handle non-ASCII symbols
    if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

    from dotenv import load_dotenv

    load_dotenv()

    required = ["SUPABASE_URL", "SUPABASE_SERVICE_KEY"]
    missing = [k for k in required if not os.getenv(k)]
    if missing:
        print(f"ERROR: Missing env vars: {missing}")
        sys.exit(1)

    asyncio.run(run_pipeline())


if __name__ == "__main__":
    main()