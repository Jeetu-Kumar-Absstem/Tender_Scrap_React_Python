"""
scraper/pipeline.py  (FIXED)
─────────────────────────────
Fixes:
  1. type_a now returns list[TenderRecord] — updated handling
  2. type_b now returns list[TenderRecord] — was already correct
  3. type_c returns list[TenderRecord] — was already correct
  4. All three scraper types now handled uniformly as lists
  5. Per-site timeout wrapper — one hung site can't block the whole run
  6. Better final log showing exactly what happened
"""

from __future__ import annotations
import asyncio
import os
import sys
import structlog
import logging
from datetime import datetime, timezone

structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.add_log_level,
        structlog.processors.JSONRenderer(),
    ],
    wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
)
log = structlog.get_logger()

from .core.schema import ACTIVE_SITES, SiteType
from .core.supabase_store import (
    create_run, finish_run, tender_exists, insert_tender, get_run_tenders
)
from .llm.extractor import get_llm_extractor
from .scrapers.type_a import scrape_type_a
from .scrapers.type_b import scrape_type_b
from .scrapers.type_c import scrape_type_c
from .email.brevo import send_digest

# Per-site timeout — prevents one slow site hanging the whole pipeline
# 15 keywords × ~60s each = ~900s needed for NIC portals
SITE_TIMEOUT_SECONDS = 900


async def _run_site(site, llm, run_id) -> list:
    """Run one site with a timeout. Returns list of TenderRecords."""
    try:
        if site.site_type == SiteType.A:
            # type_a is sync — run in executor
            loop = asyncio.get_event_loop()
            records = await asyncio.wait_for(
                loop.run_in_executor(None, scrape_type_a, site, llm, run_id),
                timeout=SITE_TIMEOUT_SECONDS,
            )
        elif site.site_type == SiteType.B:
            records = await asyncio.wait_for(
                scrape_type_b(site, llm, run_id),
                timeout=SITE_TIMEOUT_SECONDS,
            )
        elif site.site_type == SiteType.C:
            loop = asyncio.get_event_loop()
            records = await asyncio.wait_for(
                loop.run_in_executor(None, scrape_type_c, site, llm, run_id),
                timeout=SITE_TIMEOUT_SECONDS,
            )
        else:
            return []

        return records or []

    except asyncio.TimeoutError:
        log.warning("site.timeout", site=site.name, seconds=SITE_TIMEOUT_SECONDS)
        return []
    except Exception as exc:
        log.error("site.error", site=site.name, error=str(exc))
        return []


async def run_pipeline() -> None:
    log.info("pipeline.start", sites=len(ACTIVE_SITES))

    llm    = get_llm_extractor()
    run_id = create_run(sites_total=len(ACTIVE_SITES))

    sites_ok    = 0
    sites_error = 0
    new_count   = 0
    error_log: dict[str, str] = {}

    # for site in ACTIVE_SITES:
    for site in ACTIVE_SITES:
        if site.name != "Haryana":
            continue
        log.info("site.start", site=site.name, type=site.site_type.value)

        try:
            records = await _run_site(site, llm, run_id)

            if records is None:
                sites_error += 1
                continue

            sites_ok += 1

            for record in records:
                if not record or record.status != "PASS":
                    continue

                # Dedup check
                if tender_exists(record.reference_number, record.url_hash):
                    log.debug("tender.duplicate",
                              site=site.name, ref=record.reference_number)
                    continue

                inserted_id = insert_tender(record)
                if inserted_id:
                    new_count += 1
                    log.info("tender.new",
                             id=inserted_id, title=record.title, site=site.name)

        except Exception as exc:
            log.error("site.failed", site=site.name, error=str(exc))
            sites_error += 1
            error_log[site.name] = str(exc)

        await asyncio.sleep(1.5)  # polite pause between sites

    # ── Email digest ─────────────────────────────────────────
    email_sent = False
    if new_count > 0:
        new_tenders = get_run_tenders(run_id)
        email_sent  = send_digest(new_tenders, run_id=run_id)
    else:
        log.info("pipeline.no_new_tenders", message="No email sent")

    # ── Close run ────────────────────────────────────────────
    finish_run(
        run_id=run_id,
        sites_ok=sites_ok,
        sites_error=sites_error,
        new_count=new_count,
        email_sent=email_sent,
        error_log=error_log or None,
        status="failed" if sites_error == len(ACTIVE_SITES) else "completed",
    )

    log.info("pipeline.done",
             new=new_count, ok=sites_ok,
             errors=sites_error, email_sent=email_sent)


def main() -> None:
    from dotenv import load_dotenv
    load_dotenv()

    required = ["SUPABASE_URL", "SUPABASE_SERVICE_KEY"]
    missing  = [k for k in required if not os.getenv(k)]
    if missing:
        print(f"ERROR: Missing env vars: {missing}")
        sys.exit(1)

    asyncio.run(run_pipeline())


if __name__ == "__main__":
    main()