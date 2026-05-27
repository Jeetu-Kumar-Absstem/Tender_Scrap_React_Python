"""
scraper/scrapers/type_a.py
──────────────────────────
Type A scraper — Static HTML sites.
Covers: tenderdetail.com, tendersontime.com, tenderinfo.com, tender18.com, etender.in

Features:
  - Randomised User-Agent + headers
  - Exponential backoff retry (tenacity)
  - Rate limiting: max 1 req/2s per domain
  - scrape.do proxy fallback for bot-protected sites
  - Handles encoding issues common on Indian govt-adjacent sites
"""

from __future__ import annotations
import os
import random
import time
import structlog
import httpx
from typing import Optional
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

from ..core.schema import SiteConfig
from ..core.extractor import process_page
from ..core.schema import TenderRecord
from ..llm.extractor import BaseLLMExtractor

log = structlog.get_logger()

# ─── Request fingerprint pool ────────────────────────────────
_USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
]

# Simple in-memory rate limiter: track last request time per domain
_last_request: dict[str, float] = {}
_MIN_DELAY_SECONDS = 2.0


def _rate_limit(domain: str) -> None:
    """Block until at least _MIN_DELAY_SECONDS since last request to this domain."""
    last = _last_request.get(domain, 0)
    elapsed = time.time() - last
    if elapsed < _MIN_DELAY_SECONDS:
        sleep_for = _MIN_DELAY_SECONDS - elapsed + random.uniform(0, 1)
        log.debug("rate_limit.sleep", domain=domain, seconds=round(sleep_for, 2))
        time.sleep(sleep_for)
    _last_request[domain] = time.time()


def _build_headers() -> dict[str, str]:
    return {
        "User-Agent":      random.choice(_USER_AGENTS),
        "Accept":          "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-IN,en-GB;q=0.9,en;q=0.8",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection":      "keep-alive",
        "DNT":             "1",
        "Upgrade-Insecure-Requests": "1",
    }


def _extract_domain(url: str) -> str:
    from urllib.parse import urlparse
    return urlparse(url).netloc


# ─── Direct HTTP fetch ───────────────────────────────────────
@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=3, max=15),
    retry=retry_if_exception_type((httpx.HTTPError, httpx.TimeoutException)),
    reraise=True,
)
def _fetch_direct(url: str) -> str:
    domain = _extract_domain(url)
    _rate_limit(domain)

    with httpx.Client(
        timeout=20,
        follow_redirects=True,
        headers=_build_headers(),
    ) as client:
        resp = client.get(url)
        resp.raise_for_status()

        # Handle encoding — Indian sites often misclaim utf-8
        try:
            return resp.text
        except UnicodeDecodeError:
            return resp.content.decode("latin-1", errors="replace")


# ─── scrape.do proxy fetch ───────────────────────────────────
@retry(
    stop=stop_after_attempt(2),
    wait=wait_exponential(min=5, max=20),
    retry=retry_if_exception_type((httpx.HTTPError, httpx.TimeoutException)),
    reraise=True,
)
def _fetch_via_scrapedo(url: str) -> str:
    token = os.environ.get("SCRAPEDO_TOKEN", "")
    if not token:
        raise ValueError("SCRAPEDO_TOKEN not set — needed for bot-protected sites")

    api_url = (
        f"https://api.scrape.do"
        f"?token={token}"
        f"&url={url}"
        f"&render=false"           # static HTML — no JS needed
        f"&super=true"             # bypass advanced bot protection
    )
    with httpx.Client(timeout=30) as client:
        resp = client.get(api_url)
        resp.raise_for_status()
        return resp.text


# ─── Main entry point ─────────────────────────────────────────
def scrape_type_a(
    site_config: SiteConfig,
    llm: BaseLLMExtractor,
    run_id: Optional[str] = None,
) -> Optional[TenderRecord]:
    """
    Scrape one Type A (static HTML) site.
    Returns TenderRecord or None.

    Tries direct fetch first.
    If site_config.use_scrapedo=True and direct fetch fails → scrape.do fallback.
    """
    url = site_config.url
    log.info("type_a.start", site=site_config.name, url=url)

    raw_html: Optional[str] = None

    # Attempt 1: direct fetch
    try:
        raw_html = _fetch_direct(url)
        log.debug("type_a.fetched_direct", site=site_config.name, chars=len(raw_html))

    except Exception as exc:
        log.warning("type_a.direct_failed", site=site_config.name, error=str(exc))

        # Attempt 2: scrape.do (if enabled for this site)
        if site_config.use_scrapedo:
            try:
                raw_html = _fetch_via_scrapedo(url)
                log.info("type_a.fetched_via_scrapedo", site=site_config.name, chars=len(raw_html))
            except Exception as exc2:
                log.error("type_a.scrapedo_failed", site=site_config.name, error=str(exc2))
                return None
        else:
            return None

    if not raw_html:
        return None

    # Check for bot-block responses (common patterns)
    block_signals = [
        "access denied", "captcha", "cloudflare", "403 forbidden",
        "blocked", "you have been blocked", "unusual traffic",
    ]
    if any(signal in raw_html.lower() for signal in block_signals):
        log.warning("type_a.bot_blocked", site=site_config.name)
        if site_config.use_scrapedo and "scrapedo" not in url:
            # Retry via scrape.do
            try:
                raw_html = _fetch_via_scrapedo(url)
            except Exception:
                return None
        else:
            return None

    return process_page(
        raw_html=raw_html,
        site_config=site_config,
        llm=llm,
        run_id=run_id,
    )
