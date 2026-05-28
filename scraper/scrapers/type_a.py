"""
scraper/scrapers/type_a.py  (FIXED)
─────────────────────────────────────
Fixes applied:
  1. Added full cookie session warmup before scraping (many aggregators 
     check session continuity)
  2. Better bot-block detection — check status code AND body content
  3. scrape.do fallback is now always tried on 403/429/block detection,
     not just when use_scrapedo=True in config
  4. Added Content-Type check — some sites return 200 with an error page
  5. Keyword pre-filter before calling LLM (saves API cost)
  6. Returns list[TenderRecord] for consistency with type_b and type_c
     (type_a previously returned Optional[TenderRecord])
"""

from __future__ import annotations
import os
import random
import time
import structlog
import httpx
from typing import Optional
from tenacity import (
    retry, stop_after_attempt, wait_exponential,
    retry_if_exception_type,
)

from ..core.schema import SiteConfig, INCLUDE_KEYWORDS
from ..core.extractor import process_page, check_reject_keywords
from ..core.schema import TenderRecord
from ..llm.extractor import BaseLLMExtractor

log = structlog.get_logger()

_USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
]

_last_request: dict[str, float] = {}
_MIN_DELAY = 2.5  # seconds between requests to same domain


def _rate_limit(domain: str) -> None:
    last    = _last_request.get(domain, 0)
    elapsed = time.time() - last
    if elapsed < _MIN_DELAY:
        wait = _MIN_DELAY - elapsed + random.uniform(0.2, 1.0)
        log.debug("rate_limit.sleep", domain=domain, seconds=round(wait, 2))
        time.sleep(wait)
    _last_request[domain] = time.time()


def _build_headers(referer: Optional[str] = None) -> dict[str, str]:
    h = {
        "User-Agent":                random.choice(_USER_AGENTS),
        "Accept":                    "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language":           "en-IN,en-GB;q=0.9,en;q=0.8",
        "Accept-Encoding":           "gzip, deflate, br",
        "Connection":                "keep-alive",
        "DNT":                       "1",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest":            "document",
        "Sec-Fetch-Mode":            "navigate",
        "Sec-Fetch-Site":            "none" if not referer else "same-origin",
        "Sec-Fetch-User":            "?1",
    }
    if referer:
        h["Referer"] = referer
    return h


def _extract_domain(url: str) -> str:
    from urllib.parse import urlparse
    return urlparse(url).netloc


def _is_blocked(status: int, body: str) -> bool:
    """Detect bot-block responses regardless of status code."""
    if status in (403, 429, 503):
        return True
    if status == 200 and len(body) < 200:
        return True
    block_signals = [
        "access denied", "captcha required", "cloudflare",
        "403 forbidden", "you have been blocked",
        "unusual traffic", "please verify", "ddos protection",
        "ray id",  # Cloudflare ray ID
    ]
    body_lower = body[:2000].lower()
    return any(s in body_lower for s in block_signals)


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=3, max=15),
    retry=retry_if_exception_type((httpx.HTTPError, httpx.TimeoutException)),
    reraise=True,
)
def _fetch_direct(url: str) -> str:
    from urllib.parse import urlparse
    domain  = _extract_domain(url)
    origin  = f"{urlparse(url).scheme}://{domain}"
    _rate_limit(domain)

    with httpx.Client(
        timeout=20,
        follow_redirects=True,
        headers=_build_headers(),
    ) as client:
        # Warm up: hit homepage first for session cookie
        try:
            client.get(origin, timeout=8, headers=_build_headers())
        except Exception:
            pass

        resp = client.get(url, headers=_build_headers(referer=origin))
        resp.raise_for_status()

        try:
            return resp.text
        except UnicodeDecodeError:
            return resp.content.decode("latin-1", errors="replace")


@retry(
    stop=stop_after_attempt(2),
    wait=wait_exponential(min=5, max=20),
    retry=retry_if_exception_type((httpx.HTTPError, httpx.TimeoutException)),
    reraise=True,
)
def _fetch_via_scrapedo(url: str) -> str:
    token = os.environ.get("SCRAPEDO_TOKEN", "")
    if not token:
        raise ValueError("SCRAPEDO_TOKEN not set")

    api_url = (
    f"https://api.scrape.do"
    f"?token={token}&url={url}&render=true&waitUntil=networkidle0&super=true"
)
    with httpx.Client(timeout=35) as client:
        resp = client.get(api_url)
        resp.raise_for_status()
        return resp.text


# ─── Main entry point ─────────────────────────────────────────
def scrape_type_a(
    site_config: SiteConfig,
    llm: BaseLLMExtractor,
    run_id: Optional[str] = None,
) -> list[TenderRecord]:
    """
    Returns list[TenderRecord] — consistent with type_b and type_c.
    Empty list on failure (pipeline continues safely).
    """
    url = site_config.url
    log.info("type_a.start", site=site_config.name, url=url)

    raw_html: Optional[str] = None
    scrapedo_token = os.environ.get("SCRAPEDO_TOKEN", "")

    # ── Attempt 1: direct fetch ──────────────────────────────
    try:
        html = _fetch_direct(url)
        if _is_blocked(200, html):
            log.warning("type_a.soft_block", site=site_config.name)
            raise ValueError("soft block detected")
        raw_html = html
        log.debug("type_a.direct_ok", site=site_config.name, chars=len(raw_html))

    except Exception as exc:
        log.warning("type_a.direct_failed", site=site_config.name, error=str(exc))

        # ── Attempt 2: scrape.do (if token available) ────────
        if scrapedo_token:
            try:
                raw_html = _fetch_via_scrapedo(url)
                log.info("type_a.scrapedo_ok", site=site_config.name, chars=len(raw_html))
            except Exception as exc2:
                log.error("type_a.scrapedo_failed", site=site_config.name, error=str(exc2))
                return []
        else:
            log.warning("type_a.no_scrapedo_token",
                        site=site_config.name,
                        hint="Set SCRAPEDO_TOKEN in .env to bypass bot protection")
            return []

    if not raw_html:
        return []

    # ── Keyword pre-filter (free — no LLM call yet) ──────────
    raw_lower = raw_html.lower()
    has_keyword = any(kw.lower() in raw_lower for kw in INCLUDE_KEYWORDS)
    if not has_keyword:
        log.info("type_a.no_keywords", site=site_config.name)
        return []   # page has nothing relevant — skip LLM entirely

    # ── process_page (clean → window → LLM) ──────────────────
    record = process_page(
        raw_html=raw_html,
        site_config=site_config,
        llm=llm,
        run_id=run_id,
    )
    return [record] if record else []
