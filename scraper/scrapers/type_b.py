"""
scraper/scrapers/type_b.py  (FIXED)
────────────────────────────────────
Fixes applied:
  1. NIC portal uses JSF (JavaServer Faces) — IDs are dynamic like j_idt45:searchInput
     → Use XPath text-content matching and positional selectors instead of name/id
  2. Timeout increased + graceful fallback to "Active Tenders" page link
  3. Selector chain updated to match actual Haryana NIC portal HTML (from screenshot)
  4. Bot detection: NIC blocks plain httpx (JA3 fingerprint) — Playwright only
  5. Added per-site timeout so one slow site doesn't crash the browser process
  6. IREPS and HLL: use process_page with LLM (unstructured HTML)
"""

from __future__ import annotations
import asyncio
import hashlib
import random
import structlog
from datetime import datetime, timezone
from typing import Optional

from playwright.async_api import (
    async_playwright, Page, BrowserContext, Browser, TimeoutError as PWTimeout
)

from ..core.schema import SiteConfig, TenderRecord, TenderStatus, INCLUDE_KEYWORDS
from ..core.extractor import process_page
from ..llm.extractor import BaseLLMExtractor

log = structlog.get_logger()

_USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
]

_VIEWPORTS = [
    {"width": 1920, "height": 1080},
    {"width": 1536, "height": 864},
    {"width": 1440, "height": 900},
    {"width": 1366, "height": 768},
]

# ─── NIC JSF selector strategy ──────────────────────────────
# NIC portals use JSF which generates dynamic IDs like j_idt45:field
# Strategy: find by position/text/type rather than id/name
NIC_SEARCH_INPUT_SELECTORS = [
    # From screenshot: the search box is a plain <input type="text"> inside
    # the "Tender Search" widget on the right sidebar
    'input[size="20"]',                              # NIC uses size="20" consistently
    'input[maxlength="100"]',                        # common on NIC forms
    'input[type="text"][class*="search"]',
    'input[type="text"][class*="txt"]',
    'input[type="text"]',                            # last resort: first text input
]

NIC_GO_BUTTON_SELECTORS = [
    'input[value="Go"]',                             # confirmed from screenshot
    'input[type="submit"][value="Go"]',
    'input[type="button"][value="Go"]',
    'button:text-is("Go")',
    'a:text-is("Go")',
]

NIC_RESULTS_TABLE_SELECTORS = [
    # The results table confirmed from screenshot has these column headers
    'table:has(th:text-matches("Tender Title", "i"))',
    'table:has(th:text-matches("Reference No", "i"))',
    'table.list_table',
    'table[id*="tender"]',
    'table[id*="result"]',
    # JSF-generated table IDs
    'table[id*="j_idt"]',
]


async def _human_delay(min_ms: int = 700, max_ms: int = 2000) -> None:
    await asyncio.sleep(random.uniform(min_ms / 1000, max_ms / 1000))


async def _stealth_context(browser: Browser) -> BrowserContext:
    context = await browser.new_context(
        user_agent=random.choice(_USER_AGENTS),
        viewport=random.choice(_VIEWPORTS),
        locale="en-IN",
        timezone_id="Asia/Kolkata",
        extra_http_headers={
            "Accept-Language":           "en-IN,en-GB;q=0.9,en;q=0.8",
            "Accept":                    "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "DNT":                       "1",
            "Sec-Fetch-Dest":            "document",
            "Sec-Fetch-Mode":            "navigate",
            "Sec-Fetch-Site":            "none",
            "Sec-Fetch-User":            "?1",
            "Upgrade-Insecure-Requests": "1",
        },
    )
    await context.add_init_script("""
        Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
        Object.defineProperty(navigator, 'plugins',   { get: () => [1, 2, 3] });
        window.chrome = { runtime: {} };
    """)
    return context


def _normalise_date(raw: str) -> Optional[str]:
    """Convert NIC date formats to YYYY-MM-DD.
    NIC shows: '03-Jun-2026 01:00 PM'  or  '03/06/2026'
    """
    raw = raw.strip()
    if not raw or raw in ("-", "N/A", ""):
        return None
    try:
        from datetime import datetime as dt
        # DD-Mon-YYYY HH:MM AM/PM  (most common on NIC)
        return dt.strptime(raw[:11].strip(), "%d-%b-%Y").strftime("%Y-%m-%d")
    except ValueError:
        pass
    try:
        from datetime import datetime as dt
        return dt.strptime(raw[:10].strip(), "%d/%m/%Y").strftime("%Y-%m-%d")
    except ValueError:
        pass
    try:
        from datetime import datetime as dt
        return dt.strptime(raw[:10].strip(), "%Y-%m-%d").strftime("%Y-%m-%d")
    except ValueError:
        pass
    return None


async def _find_element(page: Page, selectors: list[str], timeout: int = 3000):
    """Try selectors in order, return first that is visible."""
    for sel in selectors:
        try:
            el = page.locator(sel).first
            await el.wait_for(state="visible", timeout=timeout)
            return el
        except Exception:
            continue
    return None


async def _parse_nic_table(
    page: Page,
    site_config: SiteConfig,
    run_id: Optional[str],
    keyword: str,
    base_url: str,
) -> list[TenderRecord]:
    """Parse NIC results table after search. Columns are fixed across all 33 portals."""
    records: list[TenderRecord] = []

    # Wait for table
    table_el = await _find_element(page, NIC_RESULTS_TABLE_SELECTORS, timeout=12_000)
    if not table_el:
        # Fallback: grab all page text and check if any results exist
        page_text = await page.inner_text("body")
        if "no record" in page_text.lower() or "no tender" in page_text.lower():
            log.info("nic.no_results", site=site_config.name, keyword=keyword)
        else:
            log.warning("nic.table_not_found", site=site_config.name, keyword=keyword)
        return records

    rows = table_el.locator("tr")
    count = await rows.count()
    log.debug("nic.rows_found", site=site_config.name, keyword=keyword, count=count)

    for i in range(1, count):  # skip header row
        row = rows.nth(i)
        try:
            cells = row.locator("td")
            cell_count = await cells.count()
            if cell_count < 3:
                continue

            # Title + link — always in the cell containing an <a> tag
            link_el = row.locator("td a").first
            link_count = await link_el.count()
            if link_count == 0:
                continue

            title = (await link_el.inner_text()).strip()
            href  = (await link_el.get_attribute("href")) or ""

            if not title or len(title) < 5:
                continue

            # Build absolute URL
            from urllib.parse import urlparse
            parsed = urlparse(base_url)
            if href.startswith("http"):
                detail_url = href
            elif href.startswith("/"):
                detail_url = f"{parsed.scheme}://{parsed.netloc}{href}"
            elif href:
                detail_url = f"{parsed.scheme}://{parsed.netloc}/{href.lstrip('/')}"
            else:
                detail_url = base_url

            # Reference No — typically col index 2 (0=serial, 1=title, 2=ref)
            ref_no = ""
            for col_idx in [2, 1, 3]:
                if cell_count > col_idx:
                    ref_no = (await cells.nth(col_idx).inner_text()).strip()
                    # NIC ref numbers are long hash strings or NIT/xxx format
                    if len(ref_no) > 5 and ref_no != title:
                        break

            # Closing date — typically col index 3 or 4
            deadline = None
            for col_idx in [3, 4]:
                if cell_count > col_idx:
                    raw_date = (await cells.nth(col_idx).inner_text()).strip()
                    deadline = _normalise_date(raw_date)
                    if deadline:
                        break

            url_hash = hashlib.md5(detail_url.encode()).hexdigest()
            record = TenderRecord(
                source_site=site_config.name,
                source_url=detail_url,
                site_type=site_config.site_type.value,
                run_id=run_id,
                url_hash=url_hash,
                title=title,
                reference_number=ref_no or None,
                deadline=deadline,
                keywords_matched=[keyword],
                status=TenderStatus.PASS,
                scraped_at=datetime.now(timezone.utc).isoformat(),
            )
            records.append(record)

        except Exception as exc:
            log.warning("nic.row_error", site=site_config.name, row=i, error=str(exc))
            continue

    return records


async def _scrape_nic_portal(
    page: Page,
    site_config: SiteConfig,
    run_id: Optional[str],
) -> list[TenderRecord]:
    """
    Full NIC portal scrape.
    Searches each keyword via the sidebar search box.
    Falls back to 'Active Tenders' page if sidebar search fails.
    """
    all_records: list[TenderRecord] = []
    seen_keys:   set[str]           = set()
    base_url = site_config.url

    # Navigate to homepage ONCE
    try:
        await page.goto(base_url, wait_until="domcontentloaded", timeout=30_000)
        await asyncio.sleep(1)
    except Exception as exc:
        log.error("nic.load_failed", site=site_config.name, error=str(exc))
        return []

    # Find search input ONCE — cache which selector works for this site
    cached_search_selector: Optional[str] = None
    for sel in NIC_SEARCH_INPUT_SELECTORS:
        try:
            el = page.locator(sel).first
            await el.wait_for(state="visible", timeout=3_000)
            cached_search_selector = sel
            log.debug("nic.search_selector_found", site=site_config.name, selector=sel)
            break
        except Exception:
            continue

    if not cached_search_selector:
        # Try Active Tenders link as fallback
        try:
            await page.click('a:text-matches("Active Tenders", "i")', timeout=5_000)
            await page.wait_for_load_state("domcontentloaded", timeout=10_000)
            for sel in NIC_SEARCH_INPUT_SELECTORS:
                try:
                    el = page.locator(sel).first
                    await el.wait_for(state="visible", timeout=3_000)
                    cached_search_selector = sel
                    break
                except Exception:
                    continue
        except Exception:
            log.warning("nic.no_search_input", site=site_config.name)

    for keyword in INCLUDE_KEYWORDS:
        try:
            if cached_search_selector:
                # Go back to base URL (fast — already cached by browser)
                await page.goto(base_url, wait_until="domcontentloaded", timeout=15_000)

                search_input = page.locator(cached_search_selector).first
                await search_input.wait_for(state="visible", timeout=5_000)
                await search_input.fill(keyword)  # fill() is instant, no typing delay

                go_btn = await _find_element(page, NIC_GO_BUTTON_SELECTORS, timeout=3_000)
                if go_btn:
                    await go_btn.click()
                else:
                    await page.keyboard.press("Enter")

                # Wait for results — domcontentloaded is faster than networkidle
                try:
                    await page.wait_for_load_state("domcontentloaded", timeout=10_000)
                except Exception:
                    await asyncio.sleep(2)

            else:
                log.debug("nic.fallback_homepage_table", site=site_config.name)

            # Parse results table
            records = await _parse_nic_table(page, site_config, run_id, keyword, base_url)

            # Dedup within this run
            for r in records:
                key = r.reference_number or r.url_hash
                if key not in seen_keys:
                    seen_keys.add(key)
                    all_records.append(r)

            log.info("nic.keyword_done",
                     site=site_config.name, keyword=keyword,
                     new=len(records), total=len(all_records))

            await asyncio.sleep(0.5)  # minimal polite pause

        except PWTimeout:
            log.warning("nic.timeout", site=site_config.name, keyword=keyword)
            continue
        except Exception as exc:
            log.warning("nic.keyword_error", site=site_config.name,
                        keyword=keyword, error=str(exc))
            continue

    return all_records


async def _scrape_ireps(page: Page, site_config: SiteConfig,
                        llm: BaseLLMExtractor, run_id: Optional[str]) -> list[TenderRecord]:
    try:
        await page.goto(site_config.url, wait_until="domcontentloaded", timeout=25_000)
        await _human_delay(1000, 2000)
        try:
            await page.wait_for_selector('table, .tender', timeout=8_000)
        except Exception:
            pass
        raw_html = await page.content()
        record = process_page(raw_html, site_config, llm, run_id)
        return [record] if record else []
    except Exception as exc:
        log.error("ireps.failed", error=str(exc))
        return []


async def _scrape_hll(page: Page, site_config: SiteConfig,
                      llm: BaseLLMExtractor, run_id: Optional[str]) -> list[TenderRecord]:
    try:
        await page.goto(site_config.url, wait_until="domcontentloaded", timeout=25_000)
        await _human_delay(1000, 2000)
        try:
            await page.wait_for_selector('table, .tender, .content', timeout=8_000)
        except Exception:
            pass
        raw_html = await page.content()
        record = process_page(raw_html, site_config, llm, run_id)
        return [record] if record else []
    except Exception as exc:
        log.error("hll.failed", error=str(exc))
        return []


# ─── Main entry point ─────────────────────────────────────────
async def scrape_type_b(
    site_config: SiteConfig,
    llm: BaseLLMExtractor,
    run_id: Optional[str] = None,
) -> list[TenderRecord]:
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage",
                "--disable-gpu",
                "--window-size=1366,768",
            ],
        )
        context = await _stealth_context(browser)
        page    = await context.new_page()

        # Block heavy assets — faster page loads
        await page.route(
            "**/*.{png,jpg,jpeg,gif,webp,svg,woff,woff2,ttf,eot,mp4,mp3,ico}",
            lambda r: r.abort()
        )

        try:
            url = site_config.url
            if "ireps" in url:
                results = await _scrape_ireps(page, site_config, llm, run_id)
            elif "lifecarehll" in url:
                results = await _scrape_hll(page, site_config, llm, run_id)
            else:
                results = await _scrape_nic_portal(page, site_config, run_id)

            log.info("type_b.done", site=site_config.name, records=len(results))
            return results

        except Exception as exc:
            log.error("type_b.failed", site=site_config.name, error=str(exc))
            return []
        finally:
            await context.close()
            await browser.close()