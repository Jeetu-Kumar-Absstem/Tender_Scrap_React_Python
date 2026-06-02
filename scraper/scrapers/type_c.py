"""
scraper/scrapers/type_c.py
GeM BidPlus scraper for https://bidplus.gem.gov.in/all-bids#

This keeps the original search-and-pagination behavior from the standalone
script, but emits TenderRecord rows that match the existing pipeline shape.
"""

from __future__ import annotations

import asyncio
import random
import re
from datetime import datetime
from typing import Optional
from urllib.parse import urljoin

import structlog
from playwright.async_api import Browser, BrowserContext, Page, async_playwright

from ..core.schema import INCLUDE_KEYWORDS, SiteConfig, TenderRecord, TenderStatus

log = structlog.get_logger()

_USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36",
]

_VIEWPORTS = [
    {"width": 1920, "height": 1080},
    {"width": 1600, "height": 900},
    {"width": 1536, "height": 864},
    {"width": 1366, "height": 768},
]


async def _human_delay(min_ms: int = 120, max_ms: int = 350) -> None:
    await asyncio.sleep(random.uniform(min_ms / 1000, max_ms / 1000))


async def _stealth_context(browser: Browser) -> BrowserContext:
    context = await browser.new_context(
        user_agent=random.choice(_USER_AGENTS),
        viewport=random.choice(_VIEWPORTS),
        locale="en-IN",
        timezone_id="Asia/Kolkata",
        ignore_https_errors=True,
        extra_http_headers={
            "Accept-Language": "en-IN,en-GB;q=0.9,en;q=0.8",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "DNT": "1",
        },
    )

    await context.add_init_script("""
        Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
        Object.defineProperty(navigator, 'languages', { get: () => ['en-IN', 'en-GB', 'en'] });
        window.chrome = window.chrome || { runtime: {}, loadTimes: () => {}, csi: () => {}, app: {} };
    """)
    return context


async def _abort_asset(route) -> None:
    await route.abort()


def _normalize_date(raw: str | None) -> Optional[str]:
    if not raw:
        return None
    raw = raw.strip()
    if not raw or raw == "N/A":
        return None

    for fmt in ("%d-%b-%Y", "%d/%m/%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(raw[:11].strip(), fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None


def _safe_text(value: str | None) -> Optional[str]:
    if not value:
        return None
    value = value.strip()
    return value if value and value != "N/A" else None


def _build_organization(department: str | None, organization: str | None) -> Optional[str]:
    dept = _safe_text(department)
    org = _safe_text(organization)
    if dept and org:
        return f"{dept} | {org}"
    return dept or org


async def _set_search_type(page: Page, search_type: str = "contains") -> None:
    try:
        dropdown = page.locator(".searchtype").first
        if await dropdown.count() == 0:
            return

        await dropdown.click()
        await _human_delay(250, 500)

        if search_type.lower() == "exact":
            await page.locator("xpath=//a[contains(normalize-space(.), 'Exact Search')]").first.click()
        else:
            await page.locator("xpath=//a[contains(normalize-space(.), 'Contains')]").first.click()

        await _human_delay(250, 500)
    except Exception as exc:
        log.debug("type_c.search_type_failed", error=str(exc))


async def _wait_for_results(page: Page, timeout_ms: int = 60000) -> bool:
    try:
        await page.wait_for_function(
            """() => {
                const cards = document.querySelectorAll('#bidCard .card');
                const noRecords = document.body && document.body.innerText && document.body.innerText.includes('No records found');
                return cards.length > 0 || noRecords;
            }""",
            timeout=timeout_ms,
        )
        return True
    except Exception:
        return False


async def _scrape_current_page(page: Page) -> list[dict]:
    bids_data: list[dict] = []

    cards = page.locator("#bidCard .card")
    card_count = await cards.count()
    if card_count == 0:
        return bids_data

    for idx in range(card_count):
        bid = cards.nth(idx)
        data: dict[str, str] = {}

        try:
            links = bid.locator("a.bid_no_hover")
            link_count = await links.count()
            if link_count > 0:
                first_link = links.nth(0)
                data["bid_number"] = (await first_link.inner_text()).strip()
                data["bid_url"] = await first_link.get_attribute("href") or ""
                if link_count > 1:
                    data["ra_number"] = (await links.nth(1).inner_text()).strip()
                else:
                    data["ra_number"] = "N/A"
            else:
                data["bid_number"] = "N/A"
                data["ra_number"] = "N/A"
                data["bid_url"] = ""
        except Exception:
            data["bid_number"] = "N/A"
            data["ra_number"] = "N/A"
            data["bid_url"] = ""

        try:
            item_anchor = bid.locator(".card-body .col-md-4 .row a").first
            if await item_anchor.count() > 0:
                data["items"] = (
                    await item_anchor.get_attribute("data-content")
                    or (await item_anchor.inner_text()).strip()
                )
            else:
                data["items"] = "N/A"
        except Exception:
            data["items"] = "N/A"

        try:
            qty_rows = bid.locator(".card-body .col-md-4 .row")
            if await qty_rows.count() > 1:
                qty_text = (await qty_rows.nth(1).inner_text()).strip()
                data["quantity"] = qty_text.replace("Quantity:", "").strip()
            else:
                data["quantity"] = "N/A"
        except Exception:
            data["quantity"] = "N/A"

        try:
            dept_rows = bid.locator(".card-body .col-md-5 .row")
            if await dept_rows.count() > 1:
                full_dept_text = (await dept_rows.nth(1).inner_text()).strip()
                lines = [line.strip() for line in full_dept_text.split("\n") if line.strip()]
                data["department"] = lines[0] if lines else full_dept_text
                data["organization"] = lines[1] if len(lines) > 1 else "N/A"
            else:
                data["department"] = "N/A"
                data["organization"] = "N/A"
        except Exception:
            data["department"] = "N/A"
            data["organization"] = "N/A"

        try:
            data["start_date"] = (await bid.locator(".start_date").first.inner_text()).strip()
        except Exception:
            data["start_date"] = "N/A"

        try:
            data["end_date"] = (await bid.locator(".end_date").first.inner_text()).strip()
        except Exception:
            data["end_date"] = "N/A"

        data["timestamp"] = datetime.now().isoformat()
        bids_data.append(data)

    return bids_data


async def _has_next_page(page: Page) -> bool:
    try:
        next_btn = page.locator("xpath=//a[contains(normalize-space(.), 'Next')]").first
        if await next_btn.count() == 0:
            return False
        return await next_btn.is_visible() and await next_btn.is_enabled()
    except Exception:
        return False


async def _go_to_next_page(page: Page) -> bool:
    try:
        next_btn = page.locator("xpath=//a[contains(normalize-space(.), 'Next')]").first
        if await next_btn.count() == 0:
            return False

        await next_btn.scroll_into_view_if_needed()
        await _human_delay(200, 400)
        await next_btn.click()
        await _human_delay(1200, 1800)
        return await _wait_for_results(page, timeout_ms=30000)
    except Exception as exc:
        log.debug("type_c.next_page_failed", error=str(exc))
        return False


def _make_record(
    site_config: SiteConfig,
    bid: dict,
    keyword: str,
    run_id: Optional[str],
) -> TenderRecord:
    source_url = bid.get("bid_url") or site_config.url
    title = _safe_text(bid.get("items")) or _safe_text(bid.get("bid_number"))

    return TenderRecord(
        source_site=site_config.name,
        source_url=source_url,
        site_type=site_config.site_type.value,
        run_id=run_id,
        title=title,
        reference_number=_safe_text(bid.get("bid_number")),
        organization=_build_organization(bid.get("department"), bid.get("organization")),
        deadline=_normalize_date(bid.get("end_date")),
        estimated_value=None,
        location=None,
        document_urls=[source_url] if source_url else [],
        keywords_matched=[keyword],
        status=TenderStatus.PASS.value,
    )


async def _scrape_keyword(page: Page, site_config: SiteConfig, run_id: Optional[str], keyword: str) -> list[TenderRecord]:
    all_records: list[TenderRecord] = []
    seen_refs: set[str] = set()

    try:
        search_input = page.locator("#searchBid").first
        await search_input.click(timeout=8_000)
        await _human_delay(50, 100)
        await search_input.fill("")
        await search_input.type(keyword, delay=random.randint(25, 50))
        await _human_delay(50, 120)

        await page.locator("#searchBidRA").first.click(timeout=8_000)
        await _human_delay(900, 1400)

        await _wait_for_results(page, timeout_ms=60000)

        while True:
            bids = await _scrape_current_page(page)
            for bid in bids:
                key = _safe_text(bid.get("bid_number")) or _safe_text(bid.get("bid_url")) or ""
                if not key or key in seen_refs:
                    continue
                seen_refs.add(key)
                all_records.append(_make_record(site_config, bid, keyword, run_id))

            if not await _has_next_page(page):
                break

            if not await _go_to_next_page(page):
                break

        return all_records
    except Exception as exc:
        log.warning("type_c.keyword_failed", site=site_config.name, keyword=keyword, error=str(exc))
        return all_records


async def scrape_type_c(
    site_config: SiteConfig,
    run_id: Optional[str] = None,
) -> list[TenderRecord]:
    """
    Scrape GeM BidPlus and return TenderRecord rows.
    """
    if site_config.name != "GeM BidPlus":
        log.info("type_c.unsupported_site", site=site_config.name, url=site_config.url)
        return []

    async with async_playwright() as pw:
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
                "--ignore-certificate-errors",
                "--no-first-run",
                "--no-default-browser-check",
                "--disable-infobars",
                "--window-size=1920,1080",
            ],
        )

        context = await _stealth_context(browser)
        page = await context.new_page()
        page.set_default_timeout(30_000)

        try:
            await page.route(
                "**/*.{png,jpg,jpeg,gif,webp,svg,woff,woff2,ttf,eot,mp4,mp3,ico}",
                _abort_asset,
            )

            await page.goto(site_config.url, wait_until="domcontentloaded")
            await _human_delay(4_000, 5_000)
            await _set_search_type(page, search_type="contains")

            all_records: list[TenderRecord] = []
            seen_keys: dict[str, TenderRecord] = {}

            for keyword in INCLUDE_KEYWORDS:
                records = await _scrape_keyword(page, site_config, run_id, keyword)
                for record in records:
                    key = record.reference_number or record.url_hash or record.source_url
                    existing = seen_keys.get(key)
                    if existing:
                        for kw in record.keywords_matched:
                            if kw not in existing.keywords_matched:
                                existing.keywords_matched.append(kw)
                    else:
                        seen_keys[key] = record
                        all_records.append(record)

                log.info(
                    "type_c.keyword_done",
                    site=site_config.name,
                    keyword=keyword,
                    found=len(records),
                    total_so_far=len(all_records),
                )

            log.info("type_c.done", site=site_config.name, records=len(all_records))
            return all_records
        finally:
            await context.close()
            await browser.close()
