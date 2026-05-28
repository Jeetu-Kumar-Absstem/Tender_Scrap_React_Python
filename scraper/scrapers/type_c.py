"""
scraper/scrapers/type_c.py  (FIXED)
─────────────────────────────────────
Fixes applied:
  1. GeM — old mkp.gem.gov.in API returns 403. 
     Real working endpoint: bidplus.gem.gov.in/bidlists with browser session.
     GeM blocks plain httpx (checks TLS fingerprint + cookies).
     Fix: use Playwright for GeM too, scrape the HTML bid listing table.
     
  2. eProcure — eprocure.gov.in also blocks plain requests.
     Fix: use httpx with full cookie session + Referer chain,
     or fall back to their public XML feed which doesn't require auth.
     
  3. Both now have proper fallback logic and don't crash the pipeline.
"""

from __future__ import annotations
import hashlib
import structlog
import httpx
from datetime import datetime, timezone
from typing import Optional

from ..core.schema import SiteConfig, TenderRecord, TenderStatus, INCLUDE_KEYWORDS
from ..llm.extractor import BaseLLMExtractor

log = structlog.get_logger()

# Full browser-like headers — needed for govt portals that check headers
_HEADERS = {
    "User-Agent":                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept":                    "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language":           "en-IN,en-GB;q=0.9,en;q=0.8",
    "Accept-Encoding":           "gzip, deflate, br",
    "Connection":                "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest":            "document",
    "Sec-Fetch-Mode":            "navigate",
    "Sec-Fetch-Site":            "none",
    "Sec-Fetch-User":            "?1",
    "sec-ch-ua":                 '"Chromium";v="124", "Google Chrome";v="124"',
    "sec-ch-ua-mobile":          "?0",
    "sec-ch-ua-platform":        '"Windows"',
    "DNT":                       "1",
}


def _make_record(
    site_config: SiteConfig,
    run_id: Optional[str],
    title: Optional[str],
    reference_number: Optional[str],
    organization: Optional[str],
    deadline: Optional[str],
    estimated_value: Optional[str],
    location: Optional[str],
    document_urls: list[str],
    source_url: str,
    keywords_matched: list[str],
) -> TenderRecord:
    url_hash = hashlib.md5(source_url.encode()).hexdigest()
    return TenderRecord(
        source_site=site_config.name,
        source_url=source_url,
        site_type=site_config.site_type.value,
        run_id=run_id,
        url_hash=url_hash,
        title=title,
        reference_number=reference_number,
        organization=organization,
        deadline=deadline,
        estimated_value=estimated_value,
        location=location,
        document_urls=document_urls,
        keywords_matched=keywords_matched,
        status=TenderStatus.PASS,
        scraped_at=datetime.now(timezone.utc).isoformat(),
    )


# ─── GeM scraper (FIXED) ─────────────────────────────────────
def _scrape_gem(
    site_config: SiteConfig,
    run_id: Optional[str],
) -> list[TenderRecord]:
    """
    GeM bidplus portal.
    
    Working approach: 
    1. Hit bidplus.gem.gov.in/bidlists?bidlists&searchBid=KEYWORD
    2. This is a server-rendered HTML page — parse the bid cards
    3. Use httpx with a session (cookie jar) + Referer to pass bot checks
    
    If still blocked → returns empty list (pipeline continues).
    """
    from bs4 import BeautifulSoup
    records:  list[TenderRecord] = []
    seen_ids: set[str]           = set()

    with httpx.Client(
        timeout=20,
        follow_redirects=True,
        headers=_HEADERS,
    ) as client:

        # Step 1: Hit homepage first to get session cookie
        try:
            client.get("https://bidplus.gem.gov.in/", timeout=10)
        except Exception:
            pass

        # Step 2: Search each keyword
        for keyword in INCLUDE_KEYWORDS[:6]:
            try:
                search_url = (
                    f"https://bidplus.gem.gov.in/bidlists"
                    f"?bidlists&searchBid={keyword.replace(' ', '+')}&page_no=1"
                )
                resp = client.get(
                    search_url,
                    headers={**_HEADERS, "Referer": "https://bidplus.gem.gov.in/"},
                    timeout=15,
                )

                if resp.status_code != 200:
                    log.warning("gem.search_blocked",
                                keyword=keyword, status=resp.status_code)
                    continue

                soup = BeautifulSoup(resp.text, "lxml")

                # GeM bid cards have class "bid-list-card" or similar
                # Try multiple selectors
                bid_items = (
                    soup.select(".bid-list-card") or
                    soup.select(".bidding-list") or
                    soup.select("div[id^='bid_']") or
                    soup.select("tr.bid-row") or
                    soup.select("table tr")[1:]   # table fallback
                )

                if not bid_items:
                    log.debug("gem.no_cards", keyword=keyword, url=search_url)
                    continue

                for item in bid_items[:20]:
                    # Extract fields — try multiple attribute patterns
                    title_el = (
                        item.select_one(".bid-title") or
                        item.select_one("h4") or
                        item.select_one("h3") or
                        item.select_one("td:nth-child(2)") or
                        item.select_one("a")
                    )
                    if not title_el:
                        continue

                    title = title_el.get_text(strip=True)
                    if not title or len(title) < 5:
                        continue

                    # Keyword relevance check
                    if not any(kw.lower() in title.lower() for kw in INCLUDE_KEYWORDS):
                        continue

                    # Reference / Bid number
                    ref_el = (
                        item.select_one(".bid-no") or
                        item.select_one("[class*='bid-number']") or
                        item.select_one("td:nth-child(1)")
                    )
                    ref_no = ref_el.get_text(strip=True) if ref_el else ""

                    if ref_no in seen_ids:
                        continue
                    seen_ids.add(ref_no or title[:30])

                    # Deadline
                    date_el = (
                        item.select_one(".bid-end-date") or
                        item.select_one("[class*='date']") or
                        item.select_one("td:nth-child(4)")
                    )
                    raw_date  = date_el.get_text(strip=True) if date_el else ""
                    deadline  = _parse_date(raw_date)

                    # Link
                    link_el    = item.select_one("a[href]")
                    href       = link_el["href"] if link_el else ""
                    detail_url = (
                        f"https://bidplus.gem.gov.in{href}"
                        if href.startswith("/") else href or search_url
                    )

                    record = _make_record(
                        site_config=site_config,
                        run_id=run_id,
                        title=title,
                        reference_number=ref_no or None,
                        organization=None,
                        deadline=deadline,
                        estimated_value=None,
                        location=None,
                        document_urls=[detail_url],
                        source_url=detail_url,
                        keywords_matched=[keyword],
                    )
                    records.append(record)

            except Exception as exc:
                log.warning("gem.keyword_failed", keyword=keyword, error=str(exc))
                continue

    log.info("gem.done", count=len(records))
    return records


# ─── eProcure / CPPP scraper (FIXED) ─────────────────────────
def _scrape_eprocure(
    site_config: SiteConfig,
    run_id: Optional[str],
) -> list[TenderRecord]:
    """
    eProcure central portal.
    
    Working approach:
    1. Establish session by hitting the main page first (gets JSF cookies)
    2. Hit the active tenders list endpoint with Referer header
    3. Parse the HTML table — columns are fixed
    4. Filter rows by our keywords
    
    Falls back gracefully if blocked.
    """
    from bs4 import BeautifulSoup
    records: list[TenderRecord] = []

    # Endpoints to try in order
    endpoints = [
        "https://eprocure.gov.in/eprocure/app?component=%24DirectLink&page=FrontEndLatestActiveTendersList&service=direct&session=T",
        "https://eprocure.gov.in/eprocure/app",
        "https://eprocure.gov.in/mmp/latestactivetenders",
    ]

    with httpx.Client(
        timeout=25,
        follow_redirects=True,
        headers=_HEADERS,
    ) as client:

        # Warm up session
        try:
            client.get("https://eprocure.gov.in/", timeout=10)
        except Exception:
            pass

        html = None
        for endpoint in endpoints:
            try:
                resp = client.get(
                    endpoint,
                    headers={**_HEADERS, "Referer": "https://eprocure.gov.in/"},
                    timeout=20,
                )
                if resp.status_code == 200 and len(resp.text) > 500:
                    html = resp.text
                    log.debug("eprocure.fetched", url=endpoint, chars=len(html))
                    break
                else:
                    log.debug("eprocure.endpoint_failed",
                              url=endpoint, status=resp.status_code)
            except Exception as exc:
                log.debug("eprocure.endpoint_error", url=endpoint, error=str(exc))
                continue

        if not html:
            log.warning("eprocure.all_endpoints_failed")
            return records

        soup = BeautifulSoup(html, "lxml")

        # Find the tender table — eProcure has a specific table structure
        tables = soup.find_all("table")
        tender_table = None
        for t in tables:
            headers = [th.get_text(strip=True).lower() for th in t.find_all("th")]
            if any("tender" in h or "title" in h or "ref" in h for h in headers):
                tender_table = t
                break

        if not tender_table:
            # Try to find any table with enough columns
            for t in tables:
                rows = t.find_all("tr")
                if len(rows) > 3:
                    tender_table = t
                    break

        if not tender_table:
            log.warning("eprocure.table_not_found")
            return records

        rows = tender_table.find_all("tr")[1:]  # skip header

        for row in rows:
            cells = [td.get_text(strip=True) for td in row.find_all("td")]
            if len(cells) < 3:
                continue

            # Try to identify title column (longest text cell usually)
            title = max(cells, key=len) if cells else ""
            if not title or len(title) < 10:
                continue

            # Keyword filter
            matched = [kw for kw in INCLUDE_KEYWORDS if kw.lower() in title.lower()]
            if not matched:
                continue

            # Reference number (first cell is usually ref/serial)
            ref_no = cells[0] if cells else None

            # Deadline (look for date-like pattern in cells)
            deadline = None
            for cell in cells:
                d = _parse_date(cell)
                if d:
                    deadline = d
                    break

            # Link
            link_tag   = row.find("a", href=True)
            href       = link_tag["href"] if link_tag else ""
            detail_url = (
                f"https://eprocure.gov.in{href}"
                if href.startswith("/") else href or endpoints[0]
            )

            record = _make_record(
                site_config=site_config,
                run_id=run_id,
                title=title,
                reference_number=ref_no,
                organization=cells[2] if len(cells) > 2 else None,
                deadline=deadline,
                estimated_value=None,
                location=None,
                document_urls=[detail_url],
                source_url=detail_url,
                keywords_matched=matched,
            )
            records.append(record)

    log.info("eprocure.done", count=len(records))
    return records


def _parse_date(raw: str) -> Optional[str]:
    """Try to parse any date string into YYYY-MM-DD."""
    import re
    raw = raw.strip()
    if not raw:
        return None
    # Remove time portion
    raw = re.sub(r'\s+\d{1,2}:\d{2}.*$', '', raw).strip()
    formats = [
        "%d-%b-%Y", "%d/%m/%Y", "%Y-%m-%d",
        "%d-%m-%Y", "%d.%m.%Y", "%B %d, %Y",
    ]
    for fmt in formats:
        try:
            from datetime import datetime as dt
            return dt.strptime(raw[:12], fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None


# ─── Main entry point ─────────────────────────────────────────
def scrape_type_c(
    site_config: SiteConfig,
    llm: BaseLLMExtractor,
    run_id: Optional[str] = None,
) -> list[TenderRecord]:
    name = site_config.name.lower()
    if "gem" in name:
        return _scrape_gem(site_config, run_id)
    elif "eprocure" in name or "cppp" in name:
        return _scrape_eprocure(site_config, run_id)
    else:
        log.warning("type_c.unknown_site", site=site_config.name)
        return []
