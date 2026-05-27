"""
scraper/scrapers/type_b.py
──────────────────────────
Type B scraper — NIC portal family (all 33 state portals + IREPS + HLL Lifecare)

NIC portal UI (confirmed from screenshot — etenders.hry.nic.in):
  - Sidebar "Tender Search" box: input inside #quicksearch or near the "Go" button
  - Results table: columns = Tender Title | Reference No | Closing Date | Bid Opening Date
  - Tender Title column contains clickable <a> links to detail pages
  - URL pattern: /nicgep/app?component=...&page=FrontEndAdvancedSearchResult

Strategy:
  - Type keyword into sidebar search → click "Go" → parse table rows directly
  - Table columns are FIXED across all 33 NIC portals → no LLM for listing data
  - LLM only called if we need to extract from detail page (document URLs etc.)
  - Run each keyword from INCLUDE_KEYWORDS list
  - Dedup by reference number before inserting

Bot evasion:
  - Randomised User-Agent + viewport
  - navigator.webdriver patched to undefined
  - Human-like typing delays
  - Block images/fonts/media for speed
  - Random pause between keyword searches
"""

from __future__ import annotations
import asyncio
import hashlib
import random
import re
import structlog
from datetime import datetime, timezone
from typing import Optional

from playwright.async_api import async_playwright, Page, BrowserContext, Browser

from ..core.schema import (
    SiteConfig, TenderRecord, TenderStatus, INCLUDE_KEYWORDS
)
from ..core.extractor import process_page
from ..llm.extractor import BaseLLMExtractor

log = structlog.get_logger()

# ─── Browser fingerprint pool ────────────────────────────────
_USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
]

_VIEWPORTS = [
    {"width": 1920, "height": 1080},
    {"width": 1536, "height": 864},
    {"width": 1440, "height": 900},
    {"width": 1366, "height": 768},
]

# ─── NIC portal selectors (confirmed from Haryana portal screenshot) ─
# These are identical across ALL 33 NIC state portals
NIC_SELECTORS = {
    # Sidebar search input — the text box next to the "Go" button
    "search_input": (
        'input[name*="search"],'
        'input[id*="search"],'
        'input[placeholder*="Search"],'
        'input[placeholder*="search"],'
        'input[title*="Search"],'
        'input[size="20"],'      # NIC uses size="20" on this input
        '#quicksearchText,'
        'input[name="inpTenderNo"]'
    ),

    # "Go" button next to search box
    "search_button": (
        'input[value="Go"],'
        'button:has-text("Go"),'
        'input[type="submit"][value*="Go"],'
        'input[type="button"][value*="Go"],'
        'a:has-text("Go")'
    ),

    # Results table — the tender listing table
    "results_table": (
        'table.list_table,'
        'table[id*="result"],'
        'table[id*="tender"],'
        '.tablesorter,'
        'table:has(td a[href*="TenderDetail"]),'   # table containing tender detail links
        'table:has(th:has-text("Tender Title"))'   # table with "Tender Title" header
    ),

    # Individual result rows inside the table (skip header)
    "result_rows": "tr:not(:first-child)",

    # Columns by position (0-indexed) — fixed across all NIC portals
    # Col 0: Serial No
    # Col 1: Tender Title (with link)
    # Col 2: Reference No
    # Col 3: Closing Date
    # Col 4: Bid Opening Date
    "title_cell":   "td:nth-child(2)",
    "ref_cell":     "td:nth-child(3)",
    "closing_cell": "td:nth-child(4)",
    "bidopen_cell": "td:nth-child(5)",
    "title_link":   "td:nth-child(2) a",
}


# ─── Helpers ─────────────────────────────────────────────────

async def _human_delay(min_ms: int = 600, max_ms: int = 2000) -> None:
    await asyncio.sleep(random.uniform(min_ms / 1000, max_ms / 1000))


async def _stealth_context(browser: Browser) -> BrowserContext:
    """Anti-detection browser context."""
    context = await browser.new_context(
        user_agent=random.choice(_USER_AGENTS),
        viewport=random.choice(_VIEWPORTS),
        locale="en-IN",
        timezone_id="Asia/Kolkata",
        extra_http_headers={
            "Accept-Language": "en-IN,en-GB;q=0.9,en;q=0.8",
            "Accept":          "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "DNT":             "1",
        },
    )
    # Patch: hide webdriver flag
    await context.add_init_script("""
        Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
        Object.defineProperty(navigator, 'plugins',   { get: () => [1, 2, 3] });
        window.chrome = { runtime: {} };
    """)
    return context


def _normalise_date(raw: str) -> Optional[str]:
    """
    NIC portals show dates as: '03-Jun-2026 01:00 PM'
    Convert to YYYY-MM-DD.
    """
    raw = raw.strip()
    if not raw or raw == "-":
        return None
    # Try DD-Mon-YYYY HH:MM AM/PM
    try:
        dt = datetime.strptime(raw[:11].strip(), "%d-%b-%Y")
        return dt.strftime("%Y-%m-%d")
    except ValueError:
        pass
    # Try DD/MM/YYYY
    try:
        dt = datetime.strptime(raw[:10].strip(), "%d/%m/%Y")
        return dt.strftime("%Y-%m-%d")
    except ValueError:
        pass
    return None


def _make_record(
    site_config: SiteConfig,
    run_id: Optional[str],
    title: str,
    reference_number: str,
    deadline: Optional[str],
    detail_url: str,
    keyword: str,
) -> TenderRecord:
    url_hash = hashlib.md5(detail_url.encode()).hexdigest()
    return TenderRecord(
        source_site=site_config.name,
        source_url=detail_url,
        site_type=site_config.site_type.value,
        run_id=run_id,
        url_hash=url_hash,
        title=title.strip(),
        reference_number=reference_number.strip() or None,
        organization=None,        # not shown on listing — available on detail page
        deadline=deadline,
        estimated_value=None,     # not shown on listing page
        location=None,
        document_urls=[],
        keywords_matched=[keyword],
        status=TenderStatus.PASS,
        scraped_at=datetime.now(timezone.utc).isoformat(),
    )


# ─── Parse one results table ─────────────────────────────────

async def _parse_results_table(
    page: Page,
    site_config: SiteConfig,
    run_id: Optional[str],
    keyword: str,
    base_url: str,
) -> list[TenderRecord]:
    """
    Parse the NIC tender listing table after a search.
    Returns TenderRecord list — no LLM needed (columns are fixed).
    """
    records: list[TenderRecord] = []

    try:
        # Wait for the results table to appear
        await page.wait_for_selector(
            NIC_SELECTORS["results_table"],
            timeout=12_000,
            state="visible",
        )
    except Exception:
        log.warning("nic.table_not_found", site=site_config.name, keyword=keyword)
        return records

    # Get all rows from first matching table
    table = page.locator(NIC_SELECTORS["results_table"]).first
    rows  = table.locator("tr")
    count = await rows.count()

    log.debug("nic.rows_found", site=site_config.name, keyword=keyword, rows=count)

    for i in range(1, count):   # skip header row (index 0)
        row = rows.nth(i)
        try:
            cells = row.locator("td")
            cell_count = await cells.count()
            if cell_count < 3:
                continue

            # Extract title text + href
            title_cell = row.locator(NIC_SELECTORS["title_link"])
            link_count = await title_cell.count()

            if link_count == 0:
                continue

            title      = (await title_cell.first.inner_text()).strip()
            href       = await title_cell.first.get_attribute("href") or ""

            # Build absolute URL
            if href.startswith("http"):
                detail_url = href
            elif href.startswith("/"):
                from urllib.parse import urlparse
                parsed = urlparse(base_url)
                detail_url = f"{parsed.scheme}://{parsed.netloc}{href}"
            else:
                detail_url = f"{base_url.rstrip('/')}/{href.lstrip('/')}"

            # Reference number (col 3 on NIC portals — long hash-like string)
            ref_cell  = cells.nth(2) if cell_count > 2 else None
            ref_no    = (await ref_cell.inner_text()).strip() if ref_cell else ""

            # Closing date (col 4)
            date_cell  = cells.nth(3) if cell_count > 3 else None
            raw_date   = (await date_cell.inner_text()).strip() if date_cell else ""
            deadline   = _normalise_date(raw_date)

            if not title:
                continue

            record = _make_record(
                site_config=site_config,
                run_id=run_id,
                title=title,
                reference_number=ref_no,
                deadline=deadline,
                detail_url=detail_url,
                keyword=keyword,
            )
            records.append(record)
            log.debug("nic.row_parsed", title=title[:60], ref=ref_no, deadline=deadline)

        except Exception as exc:
            log.warning("nic.row_parse_error", site=site_config.name, row=i, error=str(exc))
            continue

    return records


# ─── NIC portal search flow ──────────────────────────────────

async def _search_nic_portal(
    page: Page,
    site_config: SiteConfig,
    run_id: Optional[str],
    base_url: str,
) -> list[TenderRecord]:
    """
    For each include keyword:
      1. Type into sidebar search box
      2. Click "Go"
      3. Parse results table
      4. Collect TenderRecords
    """
    all_records: list[TenderRecord] = []
    seen_refs: set[str] = set()

    for keyword in INCLUDE_KEYWORDS:
        try:
            # Navigate/reload to homepage for fresh search
            await page.goto(base_url, wait_until="networkidle", timeout=25_000)
            await _human_delay(800, 1500)

            # Find the sidebar search input
            search_input = page.locator(NIC_SELECTORS["search_input"]).first
            input_visible = await search_input.is_visible()

            if not input_visible:
                # Fallback: try "Active Tenders" menu link
                log.debug("nic.search_not_visible_trying_active", site=site_config.name)
                try:
                    await page.click('a:has-text("Active Tenders")', timeout=5_000)
                    await page.wait_for_load_state("networkidle", timeout=15_000)
                    await _human_delay(500, 1000)
                    search_input = page.locator(NIC_SELECTORS["search_input"]).first
                except Exception:
                    pass

            # Clear, type keyword with human-like speed
            await search_input.click()
            await _human_delay(200, 400)
            await search_input.fill("")
            await search_input.type(keyword, delay=random.randint(60, 130))
            await _human_delay(300, 600)

            # Click "Go" button
            go_btn = page.locator(NIC_SELECTORS["search_button"]).first
            await go_btn.click()
            await _human_delay(1000, 2500)

            # Wait for navigation / table to appear
            try:
                await page.wait_for_load_state("networkidle", timeout=15_000)
            except Exception:
                await _human_delay(2000, 3000)

            # Parse results table
            records = await _parse_results_table(
                page=page,
                site_config=site_config,
                run_id=run_id,
                keyword=keyword,
                base_url=base_url,
            )

            # Dedup within this run by reference number
            for r in records:
                key = r.reference_number or r.url_hash
                if key not in seen_refs:
                    seen_refs.add(key)
                    all_records.append(r)

            log.info(
                "nic.keyword_done",
                site=site_config.name,
                keyword=keyword,
                found=len(records),
                total_so_far=len(all_records),
            )

            # Polite pause between keyword searches on same site
            await _human_delay(1500, 3000)

        except Exception as exc:
            log.warning(
                "nic.keyword_failed",
                site=site_config.name,
                keyword=keyword,
                error=str(exc),
            )
            continue

    return all_records


# ─── IREPS scraper ───────────────────────────────────────────

async def _scrape_ireps(
    page: Page,
    site_config: SiteConfig,
    llm: BaseLLMExtractor,
    run_id: Optional[str],
) -> list[TenderRecord]:
    await page.goto(site_config.url, wait_until="networkidle", timeout=30_000)
    await _human_delay(1000, 2000)
    raw_html = await page.content()
    record = process_page(raw_html, site_config, llm, run_id)
    return [record] if record else []


# ─── HLL Lifecare scraper ────────────────────────────────────

async def _scrape_hll(
    page: Page,
    site_config: SiteConfig,
    llm: BaseLLMExtractor,
    run_id: Optional[str],
) -> list[TenderRecord]:
    await page.goto(site_config.url, wait_until="networkidle", timeout=30_000)
    await _human_delay(1000, 2000)
    try:
        await page.wait_for_selector('.tender, table, .content', timeout=8_000)
    except Exception:
        pass
    raw_html = await page.content()
    record = process_page(raw_html, site_config, llm, run_id)
    return [record] if record else []


# ─── Main entry point ─────────────────────────────────────────

async def scrape_type_b(
    site_config: SiteConfig,
    llm: BaseLLMExtractor,
    run_id: Optional[str] = None,
) -> list[TenderRecord]:
    """
    Scrape one Type B site.
    Returns list of TenderRecords (may be multiple per keyword search).
    """
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage",
                "--disable-gpu",
            ],
        )
        context = await _stealth_context(browser)
        page    = await context.new_page()

        # Block images/fonts/media — faster, less bandwidth
        await page.route(
            "**/*.{png,jpg,jpeg,gif,webp,svg,woff,woff2,ttf,eot,mp4,mp3,ico}",
            lambda r: r.abort()
        )

        try:
            url  = site_config.url
            name = site_config.name.lower()

            if "ireps" in url:
                results = await _scrape_ireps(page, site_config, llm, run_id)
            elif "lifecarehll" in url:
                results = await _scrape_hll(page, site_config, llm, run_id)
            else:
                # All NIC state portals
                results = await _search_nic_portal(page, site_config, run_id, url)

            log.info(
                "type_b.done",
                site=site_config.name,
                records=len(results),
            )
            return results

        except Exception as exc:
            log.error("type_b.failed", site=site_config.name, error=str(exc))
            return []

        finally:
            await context.close()
            await browser.close()
