"""
run_haryana_only.py
Standalone runner — scrapes only Haryana NIC portal using type_b.py

Usage (from project root):
    python run_haryana_only.py
"""

import asyncio
import json
import structlog

from scraper.scrapers.type_b import scrape_type_b
from scraper.core.schema import SITES

log = structlog.get_logger()

# Pull Haryana config directly from schema
HARYANA_SITE = next(s for s in SITES if s.name == "Haryana")


async def main() -> None:
    log.info("runner.start", site=HARYANA_SITE.name, url=HARYANA_SITE.url)

    records = await scrape_type_b(
        site_config=HARYANA_SITE,
        run_id="haryana-manual-run",
        browser=None,
    )

    log.info("runner.done", site=HARYANA_SITE.name, total_records=len(records))

    if records:
        output_path = "haryana_tenders.json"
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump([r.to_supabase_row() for r in records], f, indent=2, ensure_ascii=False, default=str)
        print(f"\n✅  {len(records)} tender(s) saved to {output_path}")
    else:
        print("\n⚠️  No tenders found. Check debug_screenshots/ for clues.")


if __name__ == "__main__":
    asyncio.run(main())