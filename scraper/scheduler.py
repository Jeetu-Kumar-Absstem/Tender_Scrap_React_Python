"""
scraper/scheduler.py
────────────────────
Runs pipeline.main() daily at the configured time.
Uses APScheduler — stays alive as a process.

Usage:
  python -m scraper.scheduler
"""

import os
import structlog
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
from dotenv import load_dotenv

from .pipeline import main as run_pipeline

load_dotenv()
log = structlog.get_logger()

# Default: 8am IST daily
CRON_EXPR    = os.getenv("SCRAPER_CRON", "0 8 * * *")
TIMEZONE     = os.getenv("SCRAPER_TIMEZONE", "Asia/Kolkata")

scheduler = BlockingScheduler(timezone=TIMEZONE)


@scheduler.scheduled_job(CronTrigger.from_crontab(CRON_EXPR))
def daily_run():
    log.info("scheduler.trigger", cron=CRON_EXPR)
    try:
        run_pipeline()
    except Exception as exc:
        log.error("scheduler.run_failed", error=str(exc))


if __name__ == "__main__":
    log.info("scheduler.start", cron=CRON_EXPR, timezone=TIMEZONE)
    scheduler.start()
