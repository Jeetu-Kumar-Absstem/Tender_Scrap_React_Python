"""
scraper/pipeline.py
───────────────────
Daily orchestrator.

Flow:
  1. Create scrape_run record in Supabase
  2. For each active site: pick correct scraper → get TenderRecord(s)
  3. Dedup check → insert only new tenders
  4. End of run: if any new tenders → send Brevo email digest
  5. Update scrape_run with final stats

Run manually:   python -m scraper.pipeline
Run on schedule: python -m scraper.scheduler  (wraps this with APScheduler)
"""

from __future__ import annotations
import asyncio
import os
import sys
import structlog
import logging
from datetime import datetime, timezone

# ── Structured JSON logging setup ────────────────────────────
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


async def run_pipeline() -> None:
    log.info("pipeline.start", sites=len(ACTIVE_SITES))

    # ── Init ─────────────────────────────────────────────────
    llm    = get_llm_extractor()
    run_id = create_run(sites_total=len(ACTIVE_SITES))

    stats = {
        "sites_ok":    0,
        "sites_error": 0,
        "new_count":   0,
        "errors":      {},   # site_name → error message
    }

    # ── Process each site ────────────────────────────────────
    for site in ACTIVE_SITES:
        log.info("site.start", site=site.name, type=site.site_type.value)

        try:
            # Each scraper type returns different shapes:
            # Type A/B → single Optional[TenderRecord]
            # Type C   → list[TenderRecord]
            if site.site_type == SiteType.A:
                result = scrape_type_a(site, llm, run_id)
                records = [result] if result else []

            elif site.site_type == SiteType.B:
                result = await scrape_type_b(site, llm, run_id)
                records = [result] if result else []

            elif site.site_type == SiteType.C:
                records = scrape_type_c(site, llm, run_id)

            else:
                # Type D — skipped (use their alert emails instead)
                log.debug("site.skipped_type_d", site=site.name)
                continue

            stats["sites_ok"] += 1

            # ── Dedup + insert ────────────────────────────────
            for record in records:
                if record is None:
                    continue
                if record.status != "PASS":
                    continue

                already_seen = tender_exists(
                    reference_number=record.reference_number,
                    url_hash=record.url_hash,
                )
                if already_seen:
                    log.debug("tender.duplicate", site=site.name, ref=record.reference_number)
                    continue

                inserted_id = insert_tender(record)
                if inserted_id:
                    stats["new_count"] += 1
                    log.info(
                        "tender.new",
                        id=inserted_id,
                        title=record.title,
                        site=site.name,
                    )

        except Exception as exc:
            log.error("site.failed", site=site.name, error=str(exc))
            stats["sites_error"] += 1
            stats["errors"][site.name] = str(exc)

        # Polite pause between sites
        await asyncio.sleep(1.5)

    # ── Email digest ─────────────────────────────────────────
    email_sent = False
    if stats["new_count"] > 0:
        new_tenders = get_run_tenders(run_id)
        email_sent  = send_digest(new_tenders, run_id=run_id)
    else:
        log.info("pipeline.no_new_tenders")

    # ── Close run record ─────────────────────────────────────
    finish_run(
        run_id=run_id,
        sites_ok=stats["sites_ok"],
        sites_error=stats["sites_error"],
        new_count=stats["new_count"],
        email_sent=email_sent,
        error_log=stats["errors"] or None,
        status="failed" if stats["sites_error"] == len(ACTIVE_SITES) else "completed",
    )

    log.info(
        "pipeline.done",
        new=stats["new_count"],
        ok=stats["sites_ok"],
        errors=stats["sites_error"],
        email_sent=email_sent,
    )


def main() -> None:
    """Entry point for manual runs and scheduler."""
    # Load .env
    from dotenv import load_dotenv
    load_dotenv()

    # Verify required env vars
    required = ["SUPABASE_URL", "SUPABASE_SERVICE_KEY"]
    missing  = [k for k in required if not os.getenv(k)]
    if missing:
        print(f"ERROR: Missing env vars: {missing}")
        sys.exit(1)

    asyncio.run(run_pipeline())


if __name__ == "__main__":
    main()
