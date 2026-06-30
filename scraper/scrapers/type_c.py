"""
type_c.py
GeM Tender Scraper with Supabase Integration
- OPTIMIZED: ONE search per category using CATEGORY NAME
- Each PDF downloaded once and checked against ALL keywords
- Priority matching: First matching keyword (in priority order) is saved
- No re-searching, no re-downloading, no restarting from page 1
- Multiple PDF library support
- Supabase integration with CSV fallback
"""

import asyncio
import csv
import hashlib
import io
import logging
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from playwright.async_api import async_playwright

# ─── Force UTF-8 Encoding ──────────────────────────────────────────────

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# ─── PDF Library Detection ──────────────────────────────────────────────

PDF_LIB = None
PDF_LIB_NAME = None

# Try multiple PDF libraries in order
try:
    import PyPDF2
    PDF_LIB = PyPDF2
    PDF_LIB_NAME = "PyPDF2"
    print(f"[PDF] Using {PDF_LIB_NAME}")
except ImportError:
    try:
        import pypdf
        PDF_LIB = pypdf
        PDF_LIB_NAME = "pypdf"
        print(f"[PDF] Using {PDF_LIB_NAME}")
    except ImportError:
        try:
            import pdfplumber
            PDF_LIB = pdfplumber
            PDF_LIB_NAME = "pdfplumber"
            print(f"[PDF] Using {PDF_LIB_NAME}")
        except ImportError:
            print("[ERROR] No PDF library found! Install one: pip install PyPDF2")
            print("[ERROR] Or: pip install pypdf")
            print("[ERROR] Or: pip install pdfplumber")

# ─── Supabase Client ──────────────────────────────────────────────────────

try:
    from supabase import create_client
    
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

# ─── Configuration ──────────────────────────────────────────────────────

# ─── Categorized Keywords with Priority ──────────────────────────────

# Each category has keywords in priority order
# We search ONCE per category using the CATEGORY NAME
# Then check ALL keywords against each PDF

KEYWORD_CATEGORIES = {
    "psa": [
        "psa plant",           # Priority 1 - Used for searching
        "psa nitrogen plant",  # Priority 2
        "psa oxygen plant",    # Priority 3
        "psa amc",            # Priority 4
        "psa cmc",            # Priority 5
        "psa plant cmc"       # Priority 6
    ],
    "oxygen": [
        "oxygen plant",        # Priority 1 - Used for searching
        "oxygen psa plant",    # Priority 2
        "oxygen gas generation", # Priority 3
        "oxygen gas generator"  # Priority 4
            "psa oxygen"
    ],
    "nitrogen": [
        "nitrogen plant",      # Priority 1 - Used for searching
        "nitrogen psa plant",  # Priority 2
        "nitrogen gas generation", # Priority 3
        "nitrogen gas generator" ,
        "psa nitrogen",
    
    ],

    "comprehensive maintenance contract":[
        # need to refine the keywords probability is so less with these keywords
"comprehensive maintenance contract psa plant",
"comprehensive maintenance contract oxygen plant",
"comprehensive maintenance contract nitrogen plant",
"annual maintenance contract psa plant",
"annual maintenance contract oxygen plant",
"annual maintenance contract nitrogen plant",
"Comprehensive annual maintenance contract of psa oxygen generation plant",
"Comprehensive annual maintenance contract psa plant",
"Comprehensive annual maintenance contract nitrogen plant",
"preventive maintenance oxygen generator",
"oxygen plant repair maintenance",
"nitrogen plant repair maintenance",
"amc psa oxygen plant",
"cmc psa oxygen plant",
"amc psa nitrogen plant",
"cmc psa nitrogen plant",
"breakdown maintenance oxygen plant",
"breakdown maintenance nitrogen plant"
"breakdown maintenance psa plant"
"amc psa plany",
"cmc psa plant",
"customized amc/cmc for pre-owned products - psa plant",
"customized amc/cmc for pre-owned products - oxygen psa plant",
"customized amc/cmc for pre-owned products - nitrogen psa plant",
"customized amc/cmc for pre-owned products - nitrogen gas plant",
"customized amc/cmc for pre-owned products - psa oxygen generation plant",
"customized amc/cmc for pre-owned products - comprehensive annual maintenance contract of psa oxygen generation plant",
"customized amc/cmc for pre-owned products - mgpl system"
],
}


OUTPUT_DIR = Path("output")
OUTPUT_DIR.mkdir(exist_ok=True)

# ─── Logging ─────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(OUTPUT_DIR / 'scraper.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ─── Helper Functions ──────────────────────────────────────────────────

def safe_get_string(value, default="Untitled"):
    if value is None:
        return default
    return str(value)

def _normalize_date(raw: str | None) -> str | None:
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

def generate_url_hash(url: str) -> str:
    return hashlib.md5(url.encode('utf-8')).hexdigest()

def _build_organization(department: str | None, organization: str | None) -> str | None:
    dept = _safe_text(department)
    org = _safe_text(organization)
    if dept and org:
        return f"{dept} | {org}"
    return dept or org

def _safe_text(value: str | None) -> str | None:
    if not value:
        return None
    value = value.strip()
    return value if value and value != "N/A" else None

# ─── Title Cleaning Functions ──────────────────────────────────────────

def has_hindi_characters(text: str) -> bool:
    """Check if text contains Devanagari (Hindi) characters."""
    if not text:
        return False
    return bool(re.search(r'[\u0900-\u097F]', text))

def extract_english_text(text: str) -> str:
    """Extract only English text from mixed Hindi/English text."""
    if not text:
        return ""
    
    match = re.search(r'([A-Za-z0-9\s\-_,.()]+)\s*[/:]\s*[\u0900-\u097F]', text)
    if match:
        return match.group(1).strip()
    
    match = re.search(r'[\u0900-\u097F]+\s*[/:]\s*([A-Za-z0-9\s\-_,.()]+)', text)
    if match:
        return match.group(1).strip()
    
    english_words = re.findall(r'[A-Za-z][A-Za-z\s\-_,.()]+', text)
    if english_words:
        return ' '.join(english_words[:3])
    
    return ""

def clean_title(title: str) -> str:
    """Clean title - remove Hindi, keep English, remove prefixes."""
    if not title:
        return ""
    
    if has_hindi_characters(title):
        english_part = extract_english_text(title)
        if english_part:
            title = english_part
        else:
            title = re.sub(r'[\u0900-\u097F]+', '', title)
            title = ' '.join(title.split())
    
    prefixes = [
        'Custom Bid for Services - ',
        'Supply of ',
        'AMC/CMC for ',
        'Design Installation and Maintenance of ',
        'Comprehensive Maintenance Contract for ',
        'Annual Maintenance Contract for ',
        'Service Contract for ',
        'Rate Contract for ',
        'Procurement of ',
        'Supply and Installation of ',
    ]
    
    for prefix in prefixes:
        if title.lower().startswith(prefix.lower()):
            title = title[len(prefix):]
    
    title = ' '.join(title.split())
    
    if len(title) > 150:
        title = title[:147] + '...'
    
    return title.strip()

# ─── URL Fix Function ──────────────────────────────────────────────────

def get_pdf_url(bid_url: str) -> str:
    """
    Extract bid ID and build PRODUCTION URL.
    """
    if not bid_url:
        return ""
    
    bid_url = bid_url.strip()
    
    if bid_url.startswith('https://bidplus.gem.gov.in/showbidDocument/'):
        return bid_url
    
    match = re.search(r'/showbidDocument/(\d+)', bid_url)
    if match:
        bid_id = match.group(1)
        return f"https://bidplus.gem.gov.in/showbidDocument/{bid_id}"
    
    match = re.search(r'showbidDocument[/]?(\d+)', bid_url)
    if match:
        bid_id = match.group(1)
        return f"https://bidplus.gem.gov.in/showbidDocument/{bid_id}"
    
    match = re.search(r'/(\d{7,})', bid_url)
    if match:
        bid_id = match.group(1)
        return f"https://bidplus.gem.gov.in/showbidDocument/{bid_id}"
    
    if 'localhost' in bid_url or '127.0.0.1' in bid_url:
        match = re.search(r'/showbidDocument/(\d+)', bid_url)
        if match:
            bid_id = match.group(1)
            return f"https://bidplus.gem.gov.in/showbidDocument/{bid_id}"
    
    if bid_url.startswith('http'):
        match = re.search(r'/(\d{7,})', bid_url)
        if match:
            bid_id = match.group(1)
            return f"https://bidplus.gem.gov.in/showbidDocument/{bid_id}"
        return bid_url
    
    if bid_url.startswith('/showbidDocument'):
        return f"https://bidplus.gem.gov.in{bid_url}"
    
    if bid_url.startswith('showbidDocument'):
        return f"https://bidplus.gem.gov.in/{bid_url}"
    
    logger.warning(f"Could not extract bid ID from: {bid_url}")
    return ""

# ─── PDF Extraction ─────────────────────────────────────────────────────

def extract_pdf_text(pdf_url: str) -> tuple[str, str]:
    """
    Extract text from PDF using available library.
    Returns: (text, method_used)
    """
    if PDF_LIB is None:
        return "", "No PDF library available"
    
    if not pdf_url:
        return "", "No PDF URL provided"
    
    try:
        logger.debug(f"Downloading PDF from: {pdf_url}")
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/137.0.0.0 Safari/537.36',
            'Accept': 'application/pdf, text/html, */*',
            'Accept-Language': 'en-IN,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Referer': 'https://bidplus.gem.gov.in/all-bids',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'same-origin',
            'Upgrade-Insecure-Requests': '1',
            'Cache-Control': 'max-age=0',
        }
        
        session = requests.Session()
        session.headers.update(headers)
        session.cookies.set('visited', 'true')
        
        response = session.get(pdf_url, timeout=60, allow_redirects=True)
        response.raise_for_status()
        
        content = response.content
        
        content_type = response.headers.get('content-type', '').lower()
        
        if 'html' in content_type and 'pdf' not in content_type:
            logger.debug("Got HTML response, looking for PDF link...")
            
            try:
                html_text = content.decode('utf-8', errors='ignore')
            except:
                html_text = str(content)
            
            redirect_match = re.search(r'window\.location\.href\s*=\s*["\']([^"\']+)["\']', html_text)
            if redirect_match:
                pdf_path = redirect_match.group(1)
                if not pdf_path.startswith('http'):
                    pdf_path = f"https://bidplus.gem.gov.in{pdf_path}"
                logger.debug(f"Found redirect to: {pdf_path}")
                response = session.get(pdf_path, timeout=60, allow_redirects=True)
                response.raise_for_status()
                content = response.content
            else:
                pdf_match = re.search(r'href=["\']([^"\']+\.pdf)["\']', html_text, re.IGNORECASE)
                if pdf_match:
                    pdf_path = pdf_match.group(1)
                    if not pdf_path.startswith('http'):
                        pdf_path = f"https://bidplus.gem.gov.in{pdf_path}"
                    logger.debug(f"Found PDF link: {pdf_path}")
                    response = session.get(pdf_path, timeout=60, allow_redirects=True)
                    response.raise_for_status()
                    content = response.content
                else:
                    doc_match = re.search(r'href=["\']([^"\']*showbidDocument[^"\']+)["\']', html_text, re.IGNORECASE)
                    if doc_match:
                        pdf_path = doc_match.group(1)
                        if not pdf_path.startswith('http'):
                            pdf_path = f"https://bidplus.gem.gov.in{pdf_path}"
                        logger.debug(f"Found document link: {pdf_path}")
                        response = session.get(pdf_path, timeout=60, allow_redirects=True)
                        response.raise_for_status()
                        content = response.content
                    else:
                        return "", "Got HTML response, no PDF link found"
        
        if len(content) < 100:
            return "", "PDF content too small (likely invalid)"
        
        if PDF_LIB_NAME == "pdfplumber":
            return extract_pdf_pdfplumber(content), "pdfplumber"
        elif PDF_LIB_NAME == "PyPDF2":
            return extract_pdf_pypdf2(content), "PyPDF2"
        elif PDF_LIB_NAME == "pypdf":
            return extract_pdf_pypdf(content), "pypdf"
        else:
            return "", "Unknown PDF library"
            
    except requests.Timeout:
        return "", "Timeout downloading PDF"
    except requests.RequestException as e:
        return "", f"Request failed: {e}"
    except Exception as e:
        return "", f"Error: {e}"

def extract_pdf_pypdf2(content):
    try:
        pdf_file = io.BytesIO(content)
        reader = PyPDF2.PdfReader(pdf_file)
        text = ""
        for page in reader.pages:
            try:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
            except Exception:
                continue
        return text
    except Exception:
        return ""

def extract_pdf_pypdf(content):
    try:
        pdf_file = io.BytesIO(content)
        reader = pypdf.PdfReader(pdf_file)
        text = ""
        for page in reader.pages:
            try:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
            except Exception:
                continue
        return text
    except Exception:
        return ""

def extract_pdf_pdfplumber(content):
    try:
        pdf_file = io.BytesIO(content)
        text = ""
        with pdfplumber.open(pdf_file) as pdf:
            for page in pdf.pages:
                try:
                    page_text = page.extract_text()
                    if page_text:
                        text += page_text + "\n"
                except Exception:
                    continue
        return text
    except Exception:
        return ""

# ─── Exact Phrase Matching Functions ──────────────────────────────────

def exact_phrase_match(text: str, keyword: str) -> bool:
    """
    Check if the exact keyword phrase exists in the text.
    """
    if not text or not keyword:
        return False
    
    text_lower = text.lower()
    keyword_lower = keyword.lower()
    
    pattern = r'\b' + re.escape(keyword_lower) + r'\b'
    return bool(re.search(pattern, text_lower))

def simple_match(text: str, keyword: str) -> bool:
    """Uses exact phrase matching."""
    return exact_phrase_match(text, keyword)

# ─── Save Function ──────────────────────────────────────────────────

def save_to_gem_table(tender_data_list: list) -> int:
    """Save scraped tenders using ONLY webpage data for titles."""
    saved_count = 0
    client = _get_client()
    
    if client is None:
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        filename = OUTPUT_DIR / f'gem_results_{timestamp}.csv'
        if tender_data_list:
            keys = tender_data_list[0].keys()
            with open(filename, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=keys)
                writer.writeheader()
                writer.writerows(tender_data_list)
            print(f"[OK] Data saved to '{filename}' as fallback")
        return len(tender_data_list)
    
    for data in tender_data_list:
        try:
            if not data.get('bid_url'):
                print(f"   [WARN] Skipping - no URL")
                continue
            
            title = data.get('web_category') or data.get('items', '')
            title = clean_title(title)
            
            if not title or title == 'N/A' or len(title) < 5:
                bid_num = data.get('bid_number', '')
                org = data.get('organization', '')
                title = f"{bid_num} - {org}" if org else bid_num
            
            if not title:
                title = 'Untitled'
            
            url_hash = generate_url_hash(data['bid_url'])
            
            try:
                check_res = client.table("gem_tenders").select("id").eq("url_hash", url_hash).execute()
                if check_res.data and len(check_res.data) > 0:
                    print(f"   [SKIP] Duplicate: {title[:40]}...")
                    continue
            except Exception as e:
                print(f"   [WARN] Duplicate check failed: {e}")
            
            organization = data.get('organization') or data.get('department')
            
            matched_keyword = data.get('matched_keyword', '')
            matched_category = data.get('matched_category', '')
            
            row = {
                "title": title,
                "reference_number": data.get('bid_number'),
                "organization": organization,
                "deadline": _normalize_date(data.get('end_date')),
                "estimated_value": None,
                "location": None,
                "source_url": data.get('bid_url'),
                "url_hash": url_hash,
                "keywords_matched": [matched_keyword] if matched_keyword else [],
                "matched_category": matched_category,
                "scraped_at": datetime.now(timezone.utc).isoformat(),
            }
            
            try:
                res = client.table("gem_tenders").insert(row).execute()
                if res.data and len(res.data) > 0:
                    saved_count += 1
                    print(f"   [OK] Saved: {title[:50]}... (Category: {matched_category})")
                else:
                    print(f"   [WARN] Failed to save: {title[:50]}")
            except Exception as e:
                print(f"   [ERROR] Insert failed: {e}")
                
        except Exception as e:
            print(f"   [ERROR] Error saving tender: {e}")
    
    return saved_count

def archive_expired_gem_tenders(client):
    """Archive expired tenders from gem_tenders table."""
    if client is None:
        print("[ARCHIVE] No Supabase client — skipping archive sweep.")
        return 0

    today = datetime.now(timezone.utc).date().isoformat()
    print(f"\n[ARCHIVE] Starting expired-tender sweep (today = {today})...")

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
            "matched_category": tender.get("matched_category", ""),
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

# ─── Scraper Functions ──────────────────────────────────────────────────

async def _wait_for_results(page, timeout_ms: int = 60000) -> bool:
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

async def _has_next_page(page) -> bool:
    try:
        next_btn = await page.query_selector('xpath=//a[contains(normalize-space(.), "Next")]')
        if not next_btn:
            return False
        return await next_btn.is_visible() and await next_btn.is_enabled()
    except Exception:
        return False

async def _go_to_next_page(page) -> bool:
    try:
        next_btn = await page.query_selector('xpath=//a[contains(normalize-space(.), "Next")]')
        if not next_btn:
            return False
        
        await next_btn.scroll_into_view_if_needed()
        await asyncio.sleep(0.3)
        await next_btn.click()
        await asyncio.sleep(1.5)
        return await _wait_for_results(page)
    except Exception:
        return False

# ─── Main Scraper ──────────────────────────────────────────────────────

async def scrape_gem():
    """
    OPTIMIZED SCRAPER - ONE SEARCH PER CATEGORY USING CATEGORY NAME:
    
    For each category:
        1. Search using the CATEGORY NAME (e.g., "psa", "oxygen", "nitrogen")
        2. Go through ALL pages and ALL PDFs
        3. For each PDF: Download ONCE, check ALL keywords in category
        4. Stop checking keywords at first match (priority order)
        5. Save if match found, discard if no match
        6. Move to next category
    
    Benefits:
        - Only ONE search per category using category name
        - Each PDF downloaded ONCE
        - All keywords checked against each PDF
        - No re-downloading
        - No restarting from page 1
        - Much faster!
    """
    
    logger.info("=" * 60)
    logger.info("GeM Tender Scraper with Supabase")
    logger.info(f"Categories: {len(KEYWORD_CATEGORIES)}")
    total_keywords = sum(len(kw) for kw in KEYWORD_CATEGORIES.values())
    logger.info(f"Total Keywords: {total_keywords}")
    logger.info(f"PDF Library: {PDF_LIB_NAME or 'None'}")
    logger.info("=" * 60)
    
    all_results = []
    # Track processed bid URLs globally to avoid duplicates across categories
    processed_bids_global = set()
    
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage",
                "--disable-gpu",
            ]
        )
        context = await browser.new_context(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/137.0.0.0 Safari/537.36',
            viewport={'width': 1920, 'height': 1080},
            locale='en-IN',
            timezone_id='Asia/Kolkata',
            ignore_https_errors=True,
        )
        page = await context.new_page()
        
        try:
            logger.info("Navigating to https://bidplus.gem.gov.in/all-bids ...")
            await page.goto('https://bidplus.gem.gov.in/all-bids', wait_until='domcontentloaded')
            await asyncio.sleep(3)
            
            # ─── Process each category - ONE SEARCH PER CATEGORY ──────────────
            for category, keywords in KEYWORD_CATEGORIES.items():
                # Use the CATEGORY NAME as the search term
                search_term = category  # "psa", "oxygen", "nitrogen"
                
                logger.info(f"\n{'='*60}")
                logger.info(f"🎯 PROCESSING CATEGORY: '{category.upper()}'")
                logger.info(f"   Search Term: '{search_term}' (category name)")
                logger.info(f"   All Keywords to check: {keywords}")
                logger.info(f"{'='*60}")
                
                # ─── Search using the category name ──────────────────────────
                search_input = await page.query_selector('#searchBid')
                if not search_input:
                    logger.error("  ❌ Search input not found")
                    continue
                
                await search_input.click()
                await asyncio.sleep(0.1)
                await search_input.fill('')
                await search_input.type(search_term, delay=50)
                await asyncio.sleep(0.1)
                
                search_btn = await page.query_selector('#searchBidRA')
                if search_btn:
                    await search_btn.click()
                
                await asyncio.sleep(3)
                
                page_num = 1
                category_matches = 0
                pdf_count = 0
                
                # ─── Process ALL pages for this category ──────────────────────
                while True:
                    cards = await page.query_selector_all('#bidCard .card')
                    logger.info(f"  📄 Page {page_num}: Found {len(cards)} bids")
                    
                    # Process each bid on this page
                    for idx, card in enumerate(cards, 1):
                        try:
                            # Get bid information
                            bid_elem = await card.query_selector('a.bid_no_hover')
                            if not bid_elem:
                                continue
                            
                            bid_number = (await bid_elem.text_content() or "").strip()
                            bid_url = await bid_elem.get_attribute('href') or ""
                            
                            # Skip if already processed globally
                            if bid_url in processed_bids_global:
                                logger.info(f"    [{idx}] {bid_number} - Already processed globally, skipping")
                                continue
                            
                            # Build PDF URL
                            pdf_url = get_pdf_url(bid_url)
                            
                            # Get web category (title source)
                            item_elem = await card.query_selector('.card-body .col-md-4 .row a')
                            web_category = ""
                            if item_elem:
                                web_category = await item_elem.get_attribute("data-content")
                                if not web_category:
                                    web_category = await item_elem.inner_text()
                                web_category = web_category.strip() if web_category else ""
                            
                            # Get dates
                            end_elem = await card.query_selector('.end_date')
                            end_date = await end_elem.text_content() if end_elem else ""
                            
                            # Get department/organization
                            department = ""
                            organization = ""
                            dept_rows = await card.query_selector_all('.card-body .col-md-5 .row')
                            if len(dept_rows) > 1:
                                dept_text = (await dept_rows[1].text_content() or "").strip()
                                lines = [line.strip() for line in dept_text.split('\n') if line.strip()]
                                department = lines[0] if lines else ""
                                organization = lines[1] if len(lines) > 1 else ""
                            
                            logger.info(f"    [{idx}] {bid_number}")
                            logger.info(f"      📝 Web Category: {web_category[:60]}...")
                            
                            if not pdf_url:
                                logger.info(f"      ⚠️ No valid PDF URL")
                                continue
                            
                            # ─── DOWNLOAD PDF ONCE ──────────────────────────────
                            logger.info(f"      ⬇️  Downloading PDF...")
                            pdf_text, method = extract_pdf_text(pdf_url)
                            
                            if not pdf_text:
                                logger.info(f"      ❌ PDF extraction failed: {method}")
                                continue
                            
                            pdf_count += 1
                            logger.info(f"      ✅ PDF extracted ({len(pdf_text)} chars)")
                            
                            # ─── CHECK ALL KEYWORDS IN CATEGORY ──────────────────
                            # Check in priority order, stop at first match
                            matched_keyword = None
                            for priority_keyword in keywords:
                                if simple_match(pdf_text, priority_keyword):
                                    matched_keyword = priority_keyword
                                    break  # 🛑 Stop checking other keywords
                            
                            # ─── SAVE OR DISCARD ──────────────────────────────────
                            if matched_keyword:
                                logger.info(f"      ✅ MATCH FOUND! (keyword: '{matched_keyword}')")
                                
                                all_results.append({
                                    'bid_number': bid_number,
                                    'bid_url': bid_url,
                                    'pdf_url': pdf_url,
                                    'web_category': web_category,
                                    'items': web_category,
                                    'matched_keyword': matched_keyword,
                                    'matched_category': category,
                                    'department': department,
                                    'organization': organization,
                                    'end_date': end_date.strip() if end_date else "",
                                    'scraped_at': datetime.now().isoformat()
                                })
                                
                                processed_bids_global.add(bid_url)
                                category_matches += 1
                            else:
                                logger.info(f"      ❌ No match found for any keyword in category '{category}'")
                            
                            # PDF text automatically discarded when loop continues
                            
                        except Exception as e:
                            logger.error(f"      Error processing bid: {e}")
                    
                    # ─── Check if we should go to next page ──────────────────
                    if not await _has_next_page(page):
                        break
                    
                    if not await _go_to_next_page(page):
                        break
                    
                    page_num += 1
                    await asyncio.sleep(1)
                
                logger.info(f"\n  📈 Category '{category.upper()}' summary:")
                logger.info(f"     Total PDFs checked: {pdf_count}")
                logger.info(f"     Total matches found: {category_matches}")
                
                # ─── Delay between categories ─────────────────────────────────
                if list(KEYWORD_CATEGORIES.keys())[-1] != category:
                    logger.info(f"\n⏳ Waiting 3 seconds before next category...")
                    await asyncio.sleep(3)
                
        except Exception as e:
            logger.error(f"Scraping error: {e}")
        
        finally:
            await context.close()
            await browser.close()
    
    # ─── Save Data ──────────────────────────────────────────────────────────
    
    if all_results:
        print(f"\n[DATA] Total matches found: {len(all_results)}")
        
        # Remove duplicates by URL
        unique_tenders = {}
        for tender in all_results:
            url = tender.get('bid_url')
            if url and url not in unique_tenders:
                unique_tenders[url] = tender
        
        unique_list = list(unique_tenders.values())
        print(f"[DATA] {len(unique_list)} unique bids after deduplication")
        
        # Print summary by category
        print("\n[SUMMARY BY CATEGORY]")
        category_counts = {}
        for tender in unique_list:
            cat = tender.get('matched_category', 'unknown')
            category_counts[cat] = category_counts.get(cat, 0) + 1
        
        for category, count in sorted(category_counts.items()):
            print(f"  {category.upper()}: {count} tenders")
        
        # Print which keyword matched
        print("\n[MATCHED KEYWORDS BY CATEGORY]")
        keyword_counts = {}
        for tender in unique_list:
            keyword = tender.get('matched_keyword', 'unknown')
            keyword_counts[keyword] = keyword_counts.get(keyword, 0) + 1
        
        for keyword, count in sorted(keyword_counts.items(), key=lambda x: x[1], reverse=True):
            print(f"  '{keyword}': {count} tenders")
        
        # Save to Supabase
        saved = save_to_gem_table(unique_list)
        print(f"\n[OK] Saved {saved} bids to database.")
        
        # Archive expired tenders
        archive_client = _get_client()
        archived = archive_expired_gem_tenders(archive_client)
        print(f"[OK] Archived {archived} expired tender(s) from database.")
        
        # Print sample
        print("\n[Sample of matches:]")
        for i, item in enumerate(unique_list[:5], 1):
            title = safe_get_string(item.get('web_category', item.get('items')), 'Untitled')
            title = clean_title(title)
            ref = safe_get_string(item.get('bid_number'), 'No Ref')
            keyword = safe_get_string(item.get('matched_keyword'), 'Unknown')
            category = safe_get_string(item.get('matched_category'), 'Unknown')
            print(f"  {i}. {title[:60]} - {ref}")
            print(f"     Category: {category} | Matched: '{keyword}'")
        
        if len(unique_list) > 5:
            print(f"  ... and {len(unique_list) - 5} more")
    else:
        print("[WARN] No matches found.")
    
    return all_results

# ─── Main Entry Point ──────────────────────────────────────────────────────

if __name__ == '__main__':
    print("\n" + "=" * 60)
    print("GeM Tender Scraper with Supabase")
    print(f"Categories: {len(KEYWORD_CATEGORIES)}")
    total_keywords = sum(len(kw) for kw in KEYWORD_CATEGORIES.values())
    print(f"Total Keywords: {total_keywords}")
    print("=" * 60 + "\n")
    
    try:
        results = asyncio.run(scrape_gem())
        print(f"\n✅ Done! Found {len(results)} matching tenders.")
    except KeyboardInterrupt:
        print("\n⚠️ Interrupted by user")
    except Exception as e:
        print(f"\n❌ Error: {e}")