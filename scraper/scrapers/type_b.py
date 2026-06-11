"""
scraper/scrapers/type_b.py
Type B scraper for NIC portal family.

This version is Type B only:
- no LLM
- load a portal once
- submit each keyword on the same page
- parse tender rows directly from the NIC results table

Optimizations vs original:
- Accepts a shared Browser instance (launched once in pipeline, not per site)
- Human delays reduced significantly — NIC portals don't rate-limit aggressively
- Designed to be called concurrently across sites via asyncio semaphore pool
"""

from __future__ import annotations

import asyncio
import hashlib
import random
import structlog
from datetime import datetime, timezone
from typing import Optional
from urllib.parse import urljoin

from playwright.async_api import Browser, BrowserContext, Page, async_playwright

from ..core.schema import INCLUDE_KEYWORDS, SiteConfig, TenderRecord, TenderStatus

log = structlog.get_logger()

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


# ── Delays (reduced vs original — NIC portals don't aggressively rate-limit) ──

async def _human_delay(min_ms: int = 150, max_ms: int = 400) -> None:
    """Reduced from original 600–2000 ms range."""
    await asyncio.sleep(random.uniform(min_ms / 1000, max_ms / 1000))


async def _stealth_context(browser: Browser) -> BrowserContext:
    context = await browser.new_context(
        user_agent=random.choice(_USER_AGENTS),
        viewport=random.choice(_VIEWPORTS),
        locale="en-IN",
        timezone_id="Asia/Kolkata",
        extra_http_headers={
            "Accept-Language": "en-IN,en-GB;q=0.9,en;q=0.8",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "DNT": "1",
        },
    )

    await context.add_init_script("""
        Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
        Object.defineProperty(navigator, 'plugins', {
            get: () => {
                const arr = [
                    { name: 'Chrome PDF Plugin', filename: 'internal-pdf-viewer', description: 'Portable Document Format' },
                    { name: 'Chrome PDF Viewer', filename: 'mhjfbmdgcfjbbpaeojofohoefgiehjai', description: '' },
                    { name: 'Native Client', filename: 'internal-nacl-plugin', description: '' },
                ];
                arr.__proto__ = PluginArray.prototype;
                return arr;
            }
        });
        Object.defineProperty(navigator, 'languages', { get: () => ['en-IN', 'en-GB', 'en'] });
        window.chrome = { runtime: {}, loadTimes: () => {}, csi: () => {}, app: {} };
        const origQuery = window.navigator.permissions && window.navigator.permissions.query.bind(navigator.permissions);
        if (origQuery) {
            navigator.permissions.query = (parameters) =>
                parameters.name === 'notifications'
                    ? Promise.resolve({ state: Notification.permission })
                    : origQuery(parameters);
        }
        if (navigator.userAgentData) {
            Object.defineProperty(navigator, 'userAgentData', {
                get: () => ({ mobile: false, brands: [
                    { brand: 'Google Chrome', version: '124' },
                    { brand: 'Chromium', version: '124' },
                    { brand: 'Not-A.Brand', version: '99' },
                ]})
            });
        }
    """)

    return context


def _normalise_date(raw: str) -> Optional[str]:
    raw = raw.strip()
    if not raw or raw == "-":
        return None
    try:
        dt = datetime.strptime(raw[:11].strip(), "%d-%b-%Y")
        return dt.strftime("%Y-%m-%d")
    except ValueError:
        pass
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
    reference_number: Optional[str],
    deadline: Optional[str],
    detail_url: str,
    keyword: str,
) -> TenderRecord:
    return TenderRecord(
        source_site=site_config.name,
        source_url=detail_url,
        site_type=site_config.site_type.value,
        run_id=run_id,
        url_hash=hashlib.md5(detail_url.encode()).hexdigest(),
        title=title.strip() or None,
        reference_number=reference_number.strip() if reference_number else None,
        organization=None,
        deadline=deadline,
        estimated_value=None,
        location=None,
        document_urls=[],
        keywords_matched=[keyword],
        status=TenderStatus.PASS,
        scraped_at=datetime.now(timezone.utc).isoformat(),
    )


def _header_index_map(header_cells: list[str]) -> dict[str, int]:
    mapping: dict[str, int] = {}
    for idx, raw in enumerate(header_cells):
        text = " ".join(raw.lower().split())

        # Standard NIC portals — separate title column
        if "tender title" in text or "corrigendum title" in text:
            mapping["title"] = idx

        # J&K (and similar) portals — single combined "Title and Ref.No./Tender ID" column
        # Both title link and reference number live in the same <td>
        elif "title and ref" in text or "title & ref" in text:
            mapping["title"] = idx
            mapping["reference"] = idx  # same cell; ref extracted separately in parse loop

        # Standalone reference column (other portals); don't overwrite combined mapping
        elif "reference no" in text or "ref no" in text or "reference number" in text or "tender id" in text:
            if "reference" not in mapping:
                mapping["reference"] = idx

        elif "closing date" in text or "due date" in text:
            mapping["closing"] = idx

        elif "bid opening date" in text or "opening date" in text:
            mapping["bid"] = idx

    return mapping


async def _get_search_input(page: Page):
    js_find_search_input = """
        () => {
            const byName = document.querySelector(
                'input[name="SearchDescription"], #quicksearchText, input[name="inpTenderNo"], input[size="20"]'
            );
            if (byName) return byName;

            const goBtn = document.querySelector(
                'input[value="Go"], input[id="Go"], input[name="Go"], ' +
                'input[type="submit"], button[type="submit"]'
            );
            if (goBtn) {
                let el = goBtn.previousElementSibling;
                while (el) {
                    if (el.tagName === 'INPUT' && el.type !== 'hidden') return el;
                    el = el.previousElementSibling;
                }
                const parent = goBtn.parentElement;
                if (parent) {
                    const inp = parent.querySelector('input[type="text"], input:not([type])');
                    if (inp) return inp;
                }
            }

            const all = Array.from(document.querySelectorAll('input[type="text"]:not([type="hidden"])'));
            return all.find(el => el.offsetParent !== null) || null;
        }
    """

    for frame in page.frames:
        try:
            go_btn = await frame.query_selector('input[value="Go"]')
            if go_btn is None:
                continue
            handle = await frame.evaluate_handle(js_find_search_input)
            element = handle.as_element() if handle else None
            if element:
                return element
        except Exception:
            continue

    return None


async def _find_results_rows(page: Page):
    rows = page.locator('tr[id^="informal_"]')
    row_count = await rows.count()
    if row_count > 0:
        return rows
    return None


async def _find_results_table(page: Page):
    tables = page.locator(
        'table.list_table,'
        'table[id*="result"],'
        'table[id*="tender"],'
        '.tablesorter,'
        'table:has(td a[href*="TenderDetail"]),'
        'table:has(th:has-text("Tender Title"))'
    )
    count = await tables.count()
    best_table = None
    best_score = -1

    for idx in range(count):
        table = tables.nth(idx)
        try:
            text = " ".join(((await table.inner_text()) or "").lower().split())
            rows = table.locator('tr[id^="informal_"], tr.odd, tr.even')
            row_count = await rows.count()
        except Exception:
            continue

        if "tender title" not in text and "corrigendum title" not in text and "title and ref" not in text and "title & ref" not in text:
            continue

        score = row_count
        if "reference no" in text:
            score += 100
        if "bid opening date" in text:
            score += 25

        if score > best_score:
            best_score = score
            best_table = table

    return best_table


async def _get_title_link_and_text(cell) -> tuple[str, str]:
    links = cell.locator("a[href]")
    link_count = await links.count()
    for idx in range(link_count):
        link = links.nth(idx)
        try:
            text = (await link.inner_text()).strip()
            href = (await link.get_attribute("href")) or ""
        except Exception:
            continue
        if not text or len(text) < 3:
            continue
        if text.lower().endswith((".pdf", ".doc", ".docx", ".xls", ".xlsx")):
            continue
        return text, href

    try:
        text = (await cell.inner_text()).strip()
    except Exception:
        text = ""
    return text, ""


async def _parse_results_table(
    page: Page,
    site_config: SiteConfig,
    run_id: Optional[str],
    keyword: str,
    base_url: str,
) -> list[TenderRecord]:
    records: list[TenderRecord] = []
    rows = await _find_results_rows(page)
    header_map: dict[str, int] = {}

    if rows is None:
        table = await _find_results_table(page)
        if table is None:
            log.warning("nic.table_not_found", site=site_config.name, keyword=keyword)
            return records

        try:
            header_rows = table.locator("tr")
            header_count = await header_rows.count()
        except Exception:
            header_count = 0

        for idx in range(min(header_count, 5)):
            row = header_rows.nth(idx)
            try:
                raw_cells = row.locator("td,th")
                raw_count = await raw_cells.count()
                header_texts = []
                for c in range(raw_count):
                    header_texts.append((await raw_cells.nth(c).inner_text()).strip())
            except Exception:
                continue
            candidate = _header_index_map(header_texts)
            if candidate:
                header_map = candidate
                break

        rows = table.locator('tr[id^="informal_"], tr.odd, tr.even')
        row_count = await rows.count()
        if row_count == 0:
            rows = table.locator("tr")
            row_count = await rows.count()
    else:
        row_count = await rows.count()

    seen_keys: set[str] = set()

    for idx in range(row_count):
        row = rows.nth(idx)
        try:
            cells = row.locator("td")
            cell_count = await cells.count()
            if cell_count == 0:
                continue

            if header_map:
                title_idx = header_map.get("title", 0)
                ref_idx = header_map.get("reference", 1 if cell_count > 1 else 0)
                closing_idx = header_map.get("closing", 2 if cell_count > 2 else ref_idx)
            else:
                if cell_count >= 4:
                    title_idx, ref_idx, closing_idx = 0, 1, 2
                elif cell_count == 3:
                    title_idx, ref_idx, closing_idx = 0, 1, 2
                else:
                    title_idx, ref_idx, closing_idx = 0, 0, 0

            if title_idx >= cell_count:
                continue

            title_cell = cells.nth(title_idx)
            title, href = await _get_title_link_and_text(title_cell)
            if not href:
                link = row.locator("a[href]").first
                if await link.count() == 0:
                    continue
                try:
                    title = (await link.inner_text()).strip()
                    href = (await link.get_attribute("href")) or ""
                except Exception:
                    continue

            title = title.strip()
            if not title or len(title) < 3:
                continue
            if title.lower() in {"search", "view more", "view more details", "back", "home", "go"}:
                continue

            ref_no = ""
            if ref_idx < cell_count:
                try:
                    ref_cell_text = (await cells.nth(ref_idx).inner_text()).strip()
                    if ref_idx == title_idx:
                        # J&K combined column: cell looks like
                        # "[CAMC/Operationalization of Oxygen...] [MHDU/TS/2026-27/14]\n[2026_PWDJK_311911_1]"
                        # Use the last [bracketed] token as the reference number
                        import re as _re
                        bracket_matches = _re.findall(r'\[([^\]]+)\]', ref_cell_text)
                        ref_no = bracket_matches[-1].strip() if bracket_matches else ""
                    else:
                        ref_no = ref_cell_text
                except Exception:
                    ref_no = ""

            raw_date = ""
            if closing_idx < cell_count:
                try:
                    raw_date = (await cells.nth(closing_idx).inner_text()).strip()
                except Exception:
                    raw_date = ""
            deadline = _normalise_date(raw_date)

            if not ref_no and not href:
                continue

            if href.startswith("http"):
                detail_url = href
            else:
                detail_url = urljoin(base_url, href)

            key = ref_no or detail_url
            if key in seen_keys:
                continue
            seen_keys.add(key)

            records.append(
                _make_record(
                    site_config=site_config,
                    run_id=run_id,
                    title=title,
                    reference_number=ref_no or None,
                    deadline=deadline,
                    detail_url=detail_url,
                    keyword=keyword,
                )
            )
        except Exception as exc:
            log.warning("nic.row_parse_error", site=site_config.name, row=idx, error=str(exc))

    return records


async def _search_nic_portal(
    page: Page,
    site_config: SiteConfig,
    run_id: Optional[str],
    base_url: str,
) -> list[TenderRecord]:
    all_records: list[TenderRecord] = []
    seen_refs: set[str] = set()

    # Reduced from 1500–2500 ms
    await page.goto(base_url, wait_until="domcontentloaded", timeout=60_000)
    await _human_delay(400, 800)

    probe = await _get_search_input(page)
    if probe is None:
        import pathlib

        debug_dir = pathlib.Path("debug_screenshots")
        debug_dir.mkdir(exist_ok=True)
        slug = site_config.name.lower().replace(" ", "_")
        screenshot_path = debug_dir / f"{slug}_search_missing.png"
        html_path = debug_dir / f"{slug}_search_missing.html"
        try:
            await page.screenshot(path=str(screenshot_path), full_page=True)
            html_path.write_text(await page.content(), encoding="utf-8")
        except Exception:
            pass
        log.error(
            "nic.search_input_not_found",
            site=site_config.name,
            page_url=page.url,
            page_title=await page.title(),
            screenshot=str(screenshot_path),
        )
        return all_records

    for keyword in INCLUDE_KEYWORDS:
        try:
            # ── Frame-aware search: NIC portals embed the search form in an iframe ──
            async def _find_search_elements():
                """Return (frame, search_input, search_button) from whichever frame has the form."""
                for frame in page.frames:
                    try:
                        inp = frame.locator(
                            'form#tenderSearch input[name="SearchDescription"], '
                            'form#tenderSearch #SearchDescription'
                        ).first
                        btn = frame.locator(
                            'form#tenderSearch input[name="Go"], '
                            'form#tenderSearch input#Go'
                        ).first
                        if await inp.count() > 0 and await btn.count() > 0:
                            return frame, inp, btn
                    except Exception:
                        continue
                return None, None, None

            _frame, search_input, search_button = await _find_search_elements()

            if search_input is None:
                # Reload and retry once
                await page.goto(base_url, wait_until="domcontentloaded", timeout=45_000)
                await _human_delay(400, 700)
                _frame, search_input, search_button = await _find_search_elements()
                if search_input is None:
                    log.warning("nic.search_input_lost", site=site_config.name, keyword=keyword)
                    continue

            await search_input.click(timeout=8_000)
            await _human_delay(40, 80)
            await search_input.fill("")
            await search_input.type(keyword, delay=random.randint(30, 60))
            await _human_delay(40, 80)

            await search_button.click(timeout=8_000)
            await _human_delay(300, 600)  # slightly longer — give results page time to load

            try:
                await page.wait_for_url("**FrontEndAdvancedSearchResult**", timeout=8_000)
            except Exception:
                await _human_delay(300, 500)

            try:
                await page.wait_for_selector('tr[id^="informal_"]', timeout=8_000)
            except Exception:
                # Log so we know — but still attempt parse (table may use different row selector)
                log.warning(
                    "nic.no_result_rows",
                    site=site_config.name,
                    keyword=keyword,
                    page_url=page.url,
                )

            records = await _parse_results_table(
                page=page,
                site_config=site_config,
                run_id=run_id,
                keyword=keyword,
                base_url=base_url,
            )

            for record in records:
                key = record.reference_number or record.url_hash
                if key not in seen_refs:
                    seen_refs.add(key)
                    all_records.append(record)

            log.info(
                "nic.keyword_done",
                site=site_config.name,
                keyword=keyword,
                found=len(records),
                total_so_far=len(all_records),
            )

            await _human_delay(80, 200)      # Reduced from 150–350 ms

        except Exception as exc:
            log.warning("nic.keyword_failed", site=site_config.name, keyword=keyword, error=str(exc))

    return all_records

NIC_PORTAL_MARKERS = ("nicgep", "eprocure.gov.in")
async def scrape_type_b(
    site_config: SiteConfig,
    run_id: Optional[str] = None,
    browser: Optional[Browser] = None,   # NEW: accept shared browser from pipeline
) -> list[TenderRecord]:
    """
    Scrape one Type B NIC portal.

    If `browser` is provided (shared instance from pipeline), we create a new
    context on it and close only the context when done — the browser stays alive
    for the next concurrent site.

    If `browser` is None (standalone / backwards-compatible call), we launch and
    close our own browser as before.
    """
    # if "nicgep" not in site_config.url:
    if not any(marker in site_config.url for marker in NIC_PORTAL_MARKERS):

        log.info("type_b.unsupported_non_nic", site=site_config.name, url=site_config.url)
        return []

    _own_browser = browser is None  # did WE launch it, or did the pipeline?

    async def _run(b: Browser) -> list[TenderRecord]:
        context = await _stealth_context(b)
        page = await context.new_page()

        await page.route(
            "**/*.{png,jpg,jpeg,gif,webp,svg,woff,woff2,ttf,eot,mp4,mp3,ico}",
            lambda r: r.abort(),
        )

        try:
            results = await _search_nic_portal(page, site_config, run_id, site_config.url)
            log.info("type_b.done", site=site_config.name, records=len(results))
            return results
        except Exception as exc:
            log.error("type_b.failed", site=site_config.name, error=str(exc))
            return []
        finally:
            await context.close()   # always close the context
            # NOTE: do NOT close browser here — pipeline owns it

    if _own_browser:
        # Backwards-compatible: no shared browser passed in
        async with async_playwright() as pw:
            b = await pw.chromium.launch(
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
                    "--no-first-run",
                    "--no-default-browser-check",
                    "--disable-infobars",
                    "--window-size=1920,1080",
                    "--start-maximized",
                ],
            )
            try:
                return await _run(b)
            finally:
                await b.close()
    else:
        # Pipeline passed a shared browser — just use it
        return await _run(browser)