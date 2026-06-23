"""
scraper/scrapers/type_c.py
GeM BidPlus scraper for https://bidplus.gem.gov.in/all-bids#

Independent scraper like type_d.py - self-contained with its own keywords.
"""

import asyncio
import random
import re
import sys
import os
import csv
import hashlib
from datetime import datetime, timezone
from typing import Optional
from urllib.parse import urljoin

import structlog
from playwright.async_api import Browser, BrowserContext, Page, async_playwright

# ─── Keywords (independent, like type_d.py) ──────────────────────────────────

INCLUDE_KEYWORDS = [
    "psa plant", "Oxygen Generation Plant", "oxygen plant", "psa oxygen generation plant",
    "pressure swing adsorption oxygen", "medical oxygen generation plant",
    "oxygen plant sitc", "on-site oxygen generation", "oxygen generator plant",
    "oxygen gas generator", "psa oxygen", "psa nitrogen plant",
    "psa nitrogen generator", "pressure swing adsorption nitrogen",
    "nitrogen generation plant", "nitrogen plant sitc", "on-site nitrogen generation",
    "nitrogen gas generator", "psa nitrogen", "amc psa oxygen plant",
    "cmc psa oxygen plant", "annual maintenance contract oxygen plant",
    "camc psa", "comprehensive maintenance contract psa",
    "preventive maintenance oxygen generator", "service contract psa plant",
    "breakdown maintenance oxygen plant", "psa plant amc", "psa plant cmc",
    "medical gas plant maintenance", "oxygen nitrogen plant service contract",
    "mgps maintenance", "psa plant spare parts", "oxygen plant repair maintenance",
    "vpsa", "liquid oxygen", "lox", "Oxygen concentrator", "o2 plant",
    "Nitrogen concentrator", "oxygen gas plant", "camc of oxygen plant", "camc of nitrogen plant",
    "Nitrogen gas plant", "gas generation", "comprehensive maintenance contract oxygen plant",
    "comprehensive maintenance contract psa nitrogen plant"
]

# ─── Supabase Client (like type_d.py) ──────────────────────────────────────

try:
    from supabase import create_client
    import os
    
    def _get_client():
        try:
            url = os.environ.get("SUPABASE_URL")
            key = os.environ.get("SUPABASE_SERVICE_KEY")
            if url and key:
                print(f"[INIT] Creating Supabase client from env")
                return create_client(url, key)
            else:
                print(f"[WARN] Supabase env vars not set: URL={bool(url)}, KEY={bool(key)}")
        except Exception as e:
            print(f"[WARN] Failed to create Supabase client: {e}")
        return None
except ImportError:
    print("[WARN] Supabase not installed. Database saving will be disabled.")
    def _get_client():
        return None

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

# ─── Helper Functions ──────────────────────────────────────────────────────

def safe_get_string(value, default="Untitled"):
    """Safely get a string value, handling None."""
    if value is None:
        return default
    return str(value)


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


def save_to_gem_table(tender_data_list: list) -> int:
    """Save scraped tenders to the gem_tenders table (like type_d.py)."""
    saved_count = 0
    
    # Try to get Supabase client
    client = _get_client()
    
    # If no client, save to CSV as fallback
    if client is None:
        print("[WARN] No Supabase client available. Saving to CSV instead.")
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        filename = f"gem_results_{timestamp}.csv"
        if tender_data_list:
            keys = tender_data_list[0].keys()
            with open(filename, 'w', newline='', encoding='utf-8') as output_file:
                dict_writer = csv.DictWriter(output_file, fieldnames=keys)
                dict_writer.writeheader()
                dict_writer.writerows(tender_data_list)
            print(f"[OK] Data saved to '{filename}' as fallback")
        return len(tender_data_list)
    
    # Save to Supabase
    for data in tender_data_list:
        try:
            if not data.get('bid_url'):
                print(f"   [WARN] Skipping - no URL")
                continue
            
            # Generate URL hash for deduplication
            url_hash = hashlib.md5(data['bid_url'].encode('utf-8')).hexdigest()
            
            # Check for duplicate
            try:
                check_res = client.table("gem_tenders").select("id").eq("url_hash", url_hash).execute()
                if check_res.data and len(check_res.data) > 0:
                    print(f"   [SKIP] Duplicate: {safe_get_string(data.get('items'), 'Untitled')}")
                    continue
            except Exception as e:
                print(f"   [WARN] Duplicate check failed: {e}")
            
            # Build organization from department and organization
            organization = _build_organization(data.get('department'), data.get('organization'))
            
            # Insert into gem_tenders table
            row = {
                "title": data.get('items'),
                "reference_number": data.get('bid_number'),
                "organization": organization,
                "deadline": _normalize_date(data.get('end_date')),
                "estimated_value": None,  # GeM doesn't have estimated value in the same format
                "location": None,  # GeM doesn't have location in the same format
                "source_url": data.get('bid_url'),
                "url_hash": url_hash,
                "keywords_matched": [data.get('keyword')] if data.get('keyword') else [],
                "scraped_at": datetime.now(timezone.utc).isoformat(),
            }
            
            try:
                res = client.table("gem_tenders").insert(row).execute()
                if res.data and len(res.data) > 0:
                    saved_count += 1
                    print(f"   [OK] Saved: {safe_get_string(data.get('items'), 'Untitled')}")
                else:
                    print(f"   [WARN] Failed to save: {safe_get_string(data.get('items'), 'Untitled')}")
            except Exception as e:
                print(f"   [ERROR] Insert failed: {e}")
                
        except Exception as e:
            print(f"   [ERROR] Error saving tender: {e}")
    
    return saved_count


def archive_expired_gem_tenders(client):
    """Archive expired tenders from gem_tenders table (like type_d.py)."""
    if client is None:
        print("[ARCHIVE] No Supabase client — skipping archive sweep.")
        return 0

    today = datetime.now(timezone.utc).date().isoformat()
    print(f"\n[ARCHIVE] Starting expired-tender sweep (today = {today})...")

    # Fetch all live tenders whose deadline has passed
    try:
        res = client.table("gem_tenders") \
            .select("*") \
            .lt("deadline", today) \
            .is_("deleted_at", "null") \
            .execute()
        expired = res.data or []
    except Exception as e:
        print(f"[ARCHIVE] Failed to fetch expired tenders: {e}")
        return 0

    if not expired:
        print("[ARCHIVE] No expired tenders found — nothing to archive.")
        return 0

    print(f"[ARCHIVE] Found {len(expired)} expired tender(s) to archive.")

    # Fetch original_ids already in the archive
    try:
        existing_res = client.table("archive_gem_tenders") \
            .select("original_id") \
            .execute()
        already_archived = {
            row["original_id"]
            for row in (existing_res.data or [])
        }
    except Exception as e:
        print(f"[ARCHIVE] Could not fetch existing archive ids: {e}")
        already_archived = set()

    archived_count = 0
    skipped_count = 0

    for tender in expired:
        tender_id = tender.get("id")

        if tender_id in already_archived:
            print(f"   [SKIP] Already archived: {tender.get('title', tender_id)[:60]}")
            skipped_count += 1
            continue

        archive_row = {
            "original_id":      tender_id,
            "title":            tender.get("title"),
            "reference_number": tender.get("reference_number"),
            "organization":     tender.get("organization"),
            "location":         tender.get("location"),
            "deadline":         tender.get("deadline"),
            "estimated_value":  tender.get("estimated_value"),
            "source_url":       tender.get("source_url"),
            "keywords_matched": tender.get("keywords_matched", []),
            "user_status":      tender.get("user_status", "active"),
            "scraped_at":       tender.get("scraped_at"),
            "archived_at":      datetime.now(timezone.utc).isoformat(),
            "archive_reason":   "pipeline_cleanup",
        }

        try:
            ins = client.table("archive_gem_tenders").insert(archive_row).execute()
            if not (ins.data and len(ins.data) > 0):
                print(f"   [WARN] Archive insert returned no data for: {tender_id}")
                continue

            client.table("gem_tenders") \
                .update({"deleted_at": datetime.now(timezone.utc).isoformat()}) \
                .eq("id", tender_id) \
                .execute()

            archived_count += 1
            print(f"   [OK] Archived: {tender.get('title', tender_id)[:60]}")

        except Exception as e:
            print(f"   [ERROR] Failed to archive tender {tender_id}: {e}")

    print(
        f"[ARCHIVE] Done — {archived_count} archived, "
        f"{skipped_count} already in archive, "
        f"{len(expired) - archived_count - skipped_count} failed."
    )
    return archived_count


async def _scrape_keyword(page: Page, keyword: str) -> list[dict]:
    """Scrape a single keyword with pagination."""
    all_bids: list[dict] = []
    seen_refs: set[str] = set()
    page_num = 1

    try:
        print(f"   [SEARCH] Searching for: '{keyword}'")
        
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
                bid['keyword'] = keyword  # Add keyword to the bid data
                all_bids.append(bid)

            print(f"   [DATA] Page {page_num}: Found {len(bids)} bids (total: {len(all_bids)})")

            if not await _has_next_page(page):
                print(f"   [INFO] No more pages for '{keyword}'")
                break

            if not await _go_to_next_page(page):
                print(f"   [INFO] Could not go to next page for '{keyword}'")
                break
            
            page_num += 1
            await _human_delay(1000, 1500)

        print(f"   [SUMMARY] Found {len(all_bids)} total bids for '{keyword}'")
        return all_bids
        
    except Exception as exc:
        log.warning("type_c.keyword_failed", keyword=keyword, error=str(exc))
        return all_bids


async def scrape_type_c():
    """
    Main scraping function - independent like type_d.py.
    """
    print(f"\n{'='*60}")
    print(f"[START] GeM BidPlus Scraper")
    print(f"[START] Total keywords: {len(INCLUDE_KEYWORDS)}")
    print(f"{'='*60}")

    all_scraped_data = []

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

            url = "https://bidplus.gem.gov.in/all-bids"
            print(f"[NAV] Navigating to {url}...")
            await page.goto(url, wait_until="domcontentloaded")
            await _human_delay(4_000, 5_000)
            
            print("[OK] Page loaded successfully.")
            await _set_search_type(page, search_type="contains")

            processed_count = 0
            total_keywords = len(INCLUDE_KEYWORDS)

            for keyword in INCLUDE_KEYWORDS:
                processed_count += 1
                print(f"\n{'='*50}")
                print(f"[PROGRESS {processed_count}/{total_keywords}] Processing keyword: '{keyword}'")
                print(f"{'='*50}")
                
                results = await _scrape_keyword(page, keyword)
                
                if results:
                    all_scraped_data.extend(results)
                    print(f"   [TOTAL] Added {len(results)} bids from '{keyword}'")
                else:
                    print(f"   [WARN] No bids found for '{keyword}'")
                
                # Delay between keywords
                if keyword != INCLUDE_KEYWORDS[-1]:
                    print(f"   [WAIT] Waiting 2 seconds before next keyword...")
                    await _human_delay(2000, 2500)

            print(f"\n{'='*60}")
            print(f"[DONE] Scraping Complete")
            print(f"[DONE] Total bids scraped: {len(all_scraped_data)}")
            print(f"{'='*60}")

        finally:
            await context.close()
            await browser.close()

    # ─── Save Data ──────────────────────────────────────────────────────────

    if all_scraped_data:
        print(f"\n[DATA] Total bids scraped: {len(all_scraped_data)}")
        
        # Remove duplicates by URL
        unique_tenders = {}
        for tender in all_scraped_data:
            url = tender.get('bid_url')
            if url and url not in unique_tenders:
                unique_tenders[url] = tender
        
        unique_list = list(unique_tenders.values())
        print(f"[DATA] {len(unique_list)} unique bids after deduplication")
        
        # Save to gem_tenders table (or CSV as fallback)
        saved = save_to_gem_table(unique_list)
        print(f"[OK] Saved {saved} bids to database.")

        # Archive expired tenders
        archive_client = _get_client()
        archived = archive_expired_gem_tenders(archive_client)
        print(f"[OK] Archived {archived} expired tender(s) from database.")

        # Print sample
        print("\n[Sample of scraped data:]")
        for i, item in enumerate(unique_list[:5]):
            title = safe_get_string(item.get('items'), 'Untitled')
            ref = safe_get_string(item.get('bid_number'), 'No Ref')
            keyword = safe_get_string(item.get('keyword'), 'Unknown')
            print(f"  {i+1}. {title[:60]} - {ref} - [{keyword}]")
        
        if len(unique_list) > 5:
            print(f"  ... and {len(unique_list) - 5} more")
    else:
        print("[WARN] No data was scraped.")

    return all_scraped_data


# ─── Main Entry Point ──────────────────────────────────────────────────────

if __name__ == "__main__":
    import time
    asyncio.run(scrape_type_c())