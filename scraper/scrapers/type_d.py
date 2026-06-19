# scraper/scrapers/type_d.py
import asyncio
import hashlib
import os
import re
import sys
import time
from datetime import datetime, timezone

from bs4 import BeautifulSoup
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout

# Fix Windows console encoding
if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except AttributeError:
        import codecs
        sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'replace')

# --- Imports ---
try:
    from scraper.core.schema import INCLUDE_KEYWORDS
    from scraper.core.supabase_store import _get_client
    print("[INIT] Successfully imported from scraper.core")
except ImportError as e:
    print(f"[WARN] Could not import from scraper.core: {e}")
    INCLUDE_KEYWORDS = [
        "psa plant", "Oxygen Generation Plant", "oxygen plant", "psa oxygen generation plant",
        "pressure swing adsorption oxygen", "medical oxygen generation plant",
        "oxygen plant sitc", "on-site oxygen generation", "oxygen generator plant",
        "oxygen gas generator", "psa oxygen", "psa nitrogen plant",
        "psa nitrogen generator", "pressure swing adsorption nitrogen",
        "nitrogen generation plant", "nitrogen plant sitc", "on-site nitrogen generation",
        "nitrogen gas generator", "psa nitrogen", "amc psa oxygen plant",
        "cmc psa oxygen plant", "annual maintenance contract oxygen plant",
        "camc psa", "comprehensive maintenance contract",
        "preventive maintenance oxygen generator", "service contract psa plant",
        "breakdown maintenance oxygen plant", "psa plant amc", "psa plant cmc",
        "medical gas plant maintenance", "oxygen nitrogen plant service contract",
        "mgps maintenance", "psa plant spare parts", "oxygen plant repair maintenance",
        "vpsa", "liquid oxygen", "lox", "concentrator", "o2 plant",
        "gas plant", "gas generation"
    ]

    def _get_client():
        try:
            from supabase import create_client
            url = os.environ.get("SUPABASE_URL")
            key = os.environ.get("SUPABASE_SERVICE_KEY")
            if url and key:
                print("[INIT] Creating Supabase client from env")
                return create_client(url, key)
            else:
                print(f"[WARN] Supabase env vars not set: URL={bool(url)}, KEY={bool(key)}")
        except Exception as e:
            print(f"[WARN] Failed to create Supabase client: {e}")
        return None

# --- Config ---
BASE_URL   = "https://tender18.com/"
MAX_PAGES  = 3
PAGE_DELAY = 2

KEYWORDS = [kw for kw in INCLUDE_KEYWORDS if any(
    term in kw.lower() for term in ['psa', 'oxygen', 'nitrogen', 'medical', 'gas', 'o2', 'vpsa', 'lox']
)]
if not KEYWORDS:
    KEYWORDS = ["psa plant", "oxygen psa plant", "medical oxygen generation plant"]
    print("[WARN] No matching keywords found, using fallback")

print(f"[INIT] Total keywords: {len(KEYWORDS)}  |  Max pages/keyword: {MAX_PAGES}")


# --- Parsing ---
def safe_str(value, default="Untitled"):
    return str(value) if value is not None else default


def parse_tender_card(card, keyword: str) -> dict | None:
    try:
        ref_el = card.select_one('.tenders-top-left h6 span')
        ref_no = ref_el.text.strip() if ref_el else None
    except Exception:
        ref_no = None

    try:
        loc_span = card.select_one('.location h6 span')
        if loc_span:
            links = loc_span.find_all('a')
            location = ', '.join(a.text.strip() for a in links) if links else loc_span.text.strip()
        else:
            location = None
    except Exception:
        location = None

    try:
        title_el = (
            card.select_one('.tender-work h4 a span') or
            card.select_one('.tender-work h4 a') or
            card.select_one('.tender-work h4') or
            card.select_one('.tender-title') or
            card.select_one('h4')
        )
        title = title_el.text.strip() if title_el else None
    except Exception:
        title = None

    if not title and ref_no:
        title = f"Tender {ref_no}"

    try:
        agency_el = card.select_one('.tender-bottom-flex .tenders-top-left h6 span a')
        agency = agency_el.text.strip() if agency_el else None
    except Exception:
        agency = None

    try:
        val_el = card.select_one('.tender-bottom-flex .tenders-top-right h6 span')
        val = val_el.text.strip() if val_el else None
        if not val or val in ("N/A", "0", "0.00", "₹0"):
            val = "Refer to Document"
        tender_value = val
    except Exception:
        tender_value = "Refer to Document"

    try:
        date_el = card.select_one('.due-date h6 span')
        due_date = date_el.text.strip() if date_el else None
    except Exception:
        due_date = None

    try:
        url_el = card.select_one('.tender-work h4 a')
        if url_el and url_el.get('href'):
            href = url_el['href']
            detail_url = (BASE_URL.rstrip('/') + href) if href.startswith('/') else href
        else:
            detail_url = None
    except Exception:
        detail_url = None

    if not title and not ref_no:
        return None

    return {
        'ref_no':       ref_no,
        'title':        title,
        'location':     location,
        'agency':       agency,
        'tender_value': tender_value,
        'due_date':     due_date,
        'detail_url':   detail_url,
        'keyword':      keyword,
    }


# --- Supabase save ---
def save_to_tender18_table(tender_data_list: list) -> int:
    saved_count = 0
    client = _get_client()

    if client is None:
        print("[WARN] No Supabase client — skipping save.")
        return 0

    for data in tender_data_list:
        try:
            if not data.get('detail_url'):
                print("   [WARN] Skipping — no detail URL")
                continue

            url_hash = hashlib.md5(data['detail_url'].encode('utf-8')).hexdigest()

            try:
                check = client.table("tender18_tenders").select("id").eq("url_hash", url_hash).execute()
                if check.data:
                    print(f"   [SKIP] Duplicate: {safe_str(data.get('title'))[:60]}")
                    continue
            except Exception as e:
                print(f"   [WARN] Duplicate check failed: {e}")

            row = {
                "title":            data.get('title'),
                "reference_number": data.get('ref_no'),
                "organization":     data.get('agency'),
                "deadline":         data.get('due_date'),
                "estimated_value":  data.get('tender_value'),
                "location":         data.get('location'),
                "source_url":       data['detail_url'],
                "url_hash":         url_hash,
                "keywords_matched": [data['keyword']] if data.get('keyword') else [],
                "scraped_at":       datetime.now(timezone.utc).isoformat(),
            }

            res = client.table("tender18_tenders").insert(row).execute()
            if res.data:
                saved_count += 1
                print(f"   [OK] Saved: {safe_str(data.get('title'))[:60]}")
            else:
                print(f"   [WARN] Insert returned no data: {safe_str(data.get('title'))[:60]}")

        except Exception as e:
            print(f"   [ERROR] Error saving tender: {e}")

    return saved_count


# --- Playwright scraper ---
async def scrape_all() -> list:
    all_results = []

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(
            headless=True,
            args=[
                '--no-sandbox',
                '--disable-dev-shm-usage',
                '--disable-gpu',
                '--disable-blink-features=AutomationControlled',
            ]
        )
        context = await browser.new_context(
            user_agent=(
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                'AppleWebKit/537.36 (KHTML, like Gecko) '
                'Chrome/120.0.0.0 Safari/537.36'
            ),
            viewport={'width': 1920, 'height': 1080},
        )
        # Hide webdriver flag
        await context.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        )
        page = await context.new_page()

        print(f"[START] Navigating to {BASE_URL}...")
        await page.goto(BASE_URL, wait_until='domcontentloaded', timeout=30000)
        await page.wait_for_selector('#headersearch', timeout=15000)
        print("[OK] Page loaded.")

        for idx, keyword in enumerate(KEYWORDS, 1):
            print(f"\n{'='*50}")
            print(f"[PROGRESS {idx}/{len(KEYWORDS)}] Keyword: '{keyword}'")
            print(f"{'='*50}")

            kw_results = await scrape_keyword(page, keyword)
            all_results.extend(kw_results)
            print(f"   [TOTAL] {len(kw_results)} tenders for '{keyword}'")

            if idx < len(KEYWORDS):
                await asyncio.sleep(PAGE_DELAY)

        await browser.close()

    return all_results


async def scrape_keyword(page, keyword: str) -> list:
    results = []

    for page_num in range(1, MAX_PAGES + 1):
        # Navigate home and search on first page
        if page_num == 1:
            success = await do_search(page, keyword)
            if not success:
                print(f"   [ERROR] Search failed for '{keyword}'")
                break
        else:
            went = await go_next_page(page)
            if not went:
                print(f"   [INFO] No more pages after page {page_num - 1}")
                break

        # Wait for results
        try:
            await page.wait_for_selector('div.live-tenders-block', timeout=10000)
        except PlaywrightTimeout:
            print(f"   [WARN] No results on page {page_num}")
            break

        await asyncio.sleep(1.5)
        html  = await page.content()
        soup  = BeautifulSoup(html, 'html.parser')
        cards = soup.select('div.live-tenders-block')

        page_results = []
        for card in cards:
            parsed = parse_tender_card(card, keyword)
            if parsed:
                page_results.append(parsed)

        print(f"   [DATA] Page {page_num}: {len(page_results)} tenders")
        results.extend(page_results)

        if not page_results:
            break

        if await is_last_page(page):
            print(f"   [INFO] Last page reached.")
            break

    return results


async def do_search(page, keyword: str) -> bool:
    try:
        await page.goto(BASE_URL, wait_until='domcontentloaded', timeout=30000)
        await page.wait_for_selector('#headersearch', timeout=10000)

        search_input = page.locator('#headersearch')
        await search_input.click()
        await search_input.fill('')
        await search_input.fill(keyword)
        print(f"   [OK] Entered keyword: '{keyword}'")

        submit = page.locator("input.submit[value='Search']")
        await submit.click()
        print(f"   [OK] Search submitted.")
        return True
    except Exception as e:
        print(f"   [ERROR] Search failed: {e}")
        return False


async def go_next_page(page) -> bool:
    try:
        # Strategy 1: button with Next text not in disabled li
        next_btns = page.locator(
            "li:not(.disabled) button:has-text('Next'), "
            "li:not(.disabled) button:has-text('›'), "
            "li:not(.disabled) button:has-text('»')"
        )
        if await next_btns.count() > 0:
            await next_btns.first.scroll_into_view_if_needed()
            await next_btns.first.click()
            await asyncio.sleep(1)
            return True

        # Strategy 2: aria-label
        aria_next = page.locator("[aria-label='Next'], [aria-label='Next Page']")
        if await aria_next.count() > 0:
            await aria_next.first.click()
            await asyncio.sleep(1)
            return True

        # Strategy 3: find active page number and click next number
        active = page.locator(".page-item.active .page-link, .pagination .active a")
        if await active.count() > 0:
            current_text = await active.first.inner_text()
            try:
                current = int(current_text.strip())
                next_link = page.locator(f".page-link:has-text('{current + 1}')")
                if await next_link.count() > 0:
                    await next_link.first.click()
                    await asyncio.sleep(1)
                    return True
            except ValueError:
                pass

        return False
    except Exception as e:
        print(f"   [WARN] go_next_page error: {e}")
        return False


async def is_last_page(page) -> bool:
    try:
        disabled_next = page.locator(
            "li.disabled button:has-text('Next'), "
            "li.disabled button:has-text('›')"
        )
        return await disabled_next.count() > 0
    except Exception:
        return False


# --- Entry point ---
async def main():
    all_data = await scrape_all()

    print(f"\n{'='*50}")
    print(f"[DONE] Total tenders scraped: {len(all_data)}")
    print(f"{'='*50}")

    if not all_data:
        print("[WARN] No data scraped.")
        return

    # Deduplicate by URL
    unique: dict = {}
    for t in all_data:
        url = t.get('detail_url')
        if url and url not in unique:
            unique[url] = t
    unique_list = list(unique.values())
    print(f"[DATA] {len(unique_list)} unique tenders after dedup")

    saved = save_to_tender18_table(unique_list)
    print(f"[OK] Saved {saved} new tenders to database.")

    print("\n[Sample:]")
    for i, item in enumerate(unique_list[:5]):
        print(f"  {i+1}. {safe_str(item.get('title'))[:60]} [{item.get('keyword')}]")
    if len(unique_list) > 5:
        print(f"  ... and {len(unique_list) - 5} more")


if __name__ == '__main__':
    asyncio.run(main())
else:
    # Invoked via `python -m scraper.scrapers.type_d`
    asyncio.run(main())