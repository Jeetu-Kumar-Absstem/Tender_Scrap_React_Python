"""
scraper/pipeline.py
Daily orchestrator for Type B plus HLL Lifecare plus GeM BidPlus.

Flow:
  1. Create scrape_run record in Supabase
  2. Launch ONE shared browser
  3. Run Type B sites concurrently, HLL Lifecare via Type A, and GeM BidPlus via Type C
  4. Dedup check -> insert only new tenders  (still serial per record, safe for Supabase)
  5. End of run: if any new tenders -> send Brevo email digest
  6. Update scrape_run with final stats
  7. Close shared browser

Optimizations vs original:
  - One browser launched once, shared across all sites (saves ~35 launch/close cycles)
  - Sites run in parallel with a semaphore cap of CONCURRENCY (default 5)
  - asyncio.sleep between sites removed (parallelism makes it irrelevant)
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
from .core.supabase_store import create_run, finish_run, get_run_tenders, insert_tender, tender_exists
from .email.brevo import send_digest
from .scrapers.type_a import scrape_type_a
from .scrapers.type_b import scrape_type_b
from .scrapers.type_c import scrape_type_c

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
# Raise to 8–10 if your machine has >16 GB RAM and you want more speed.
CONCURRENCY = 3


# Asyncio lock to serialize Supabase writes (not thread-safe)
_db_lock = asyncio.Lock()


async def _scrape_site(
    site: SiteConfig,
    run_id: str,
    browser: Browser,
    sem: asyncio.Semaphore,
    stats: dict,
) -> tuple[SiteConfig, int, Optional[str]]:
    """
    Scrape one site under the semaphore.
    Inserts new tenders into DB immediately as site completes.
    Returns (site, new_count, error_message_or_None).
    """
    async with sem:
        log.info("site.start", site=site.name, type=site.site_type.value)
        try:
            if site.site_type == SiteType.B:
                records = await scrape_type_b(site, run_id=run_id, browser=browser)
            elif site.site_type == SiteType.A and site.name == "HLL Lifecare":
                records = await asyncio.to_thread(scrape_type_a, site, run_id)
            elif site.site_type == SiteType.C and site.name == "GeM BidPlus":
                records = await scrape_type_c(site, run_id=run_id)
            else:
                log.info("site.skipped", site=site.name, type=site.site_type.value)
                return site, 0, None

            # ── Insert immediately, don't wait for all sites ────
            new_count = 0
            async with _db_lock:
                for record in records:
                    if record is None or record.status != "PASS":
                        continue
                    already_seen = tender_exists(
                        reference_number=record.reference_number,
                        url_hash=record.url_hash,
                    )
                    if already_seen:
                        log.debug("tender.duplicate", site=site.name,
                                  ref=record.reference_number)
                        continue
                    inserted_id = insert_tender(record)
                    if inserted_id:
                        new_count += 1
                        stats["new_count"] += 1
                        log.info("tender.new", id=inserted_id,
                                 title=record.title, site=site.name)

            log.info("site.done", site=site.name, records=len(records),
                     new=new_count)
            return site, new_count, None

        except Exception as exc:
            log.error("site.failed", site=site.name, error=str(exc))
            return site, 0, str(exc)


async def run_pipeline() -> None:
    sites = (
         [s for s in SITES_BY_TYPE[SiteType.A] if s.name == "HLL Lifecare"]
        + [s for s in SITES_BY_TYPE[SiteType.C] if s.name == "GeM BidPlus"]
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

    async with async_playwright() as pw:
        # ── Launch ONE shared browser for all sites ──────────────
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

            # ── Fire all sites concurrently, capped by semaphore ─
            tasks = [
                _scrape_site(site, run_id, browser, sem, stats)
                for site in sites
            ]
            results = await asyncio.gather(*tasks, return_exceptions=False)

        finally:
            await browser.close()
            log.info("pipeline.browser_closed")

    # ── Tally results (inserts already done inside _scrape_site) ─
    for site, new_count, error in results:
        if error:
            stats["sites_error"] += 1
            stats["errors"][site.name] = error
        else:
            stats["sites_ok"] += 1

    # ── Email digest ─────────────────────────────────────────────
    email_sent = False
    if stats["new_count"] > 0:
        new_tenders = get_run_tenders(run_id)
        email_sent = send_digest(new_tenders, run_id=run_id)
    else:
        log.info("pipeline.no_new_tenders")

    # ── Finalise run ─────────────────────────────────────────────
    finish_run(
        run_id=run_id,
        sites_ok=stats["sites_ok"],
        sites_error=stats["sites_error"],
        new_count=stats["new_count"],
        email_sent=email_sent,
        error_log=stats["errors"] or None,
        status="failed" if stats["sites_error"] == len(sites) else "completed",
    )

    log.info(
        "pipeline.done",
        new=stats["new_count"],
        ok=stats["sites_ok"],
        errors=stats["sites_error"],
        email_sent=email_sent,
    )


def main() -> None:
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