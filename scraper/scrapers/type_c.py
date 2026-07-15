"""
type_c.py
GeM Tender Scraper with Supabase Integration
- COMPLETE FLOW: Extract ref number BEFORE PDF download
- Store ALL reference numbers in processed_references
- Store ONLY matching tenders in gem_tenders
- Skip already processed bids (no PDF download, no keyword check)
- Bulk insert with counters
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

# KEYWORD_CATEGORIES = {
#     "psa": [
#         "psa plant",
#         "psa nitrogen plant",
#         "psa oxygen plant",
#         "psa amc",
#         "psa cmc",
#         "psa plant cmc"
#     ],
#     "oxygen": [
#         "oxygen plant",
#         "oxygen psa plant",
#         "oxygen gas generation",
#         "oxygen gas generator",
#         "psa oxygen",
#         "oxygen generation plant",
#         "On-site oxygen generation system",
#         "Oxygen concentrator plant",
#         "District hospital oxygen plant",
#         "Medical college oxygen plant",
#     ],
#     "nitrogen": [
#         "nitrogen plant",
#         "nitrogen psa plant",
#         "nitrogen gas generation",
#         "nitrogen gas generator",
#         "psa nitrogen",
#         "nitrogen generation plant",
#         "On-site nitrogen generation system"
#     ],
#     "comprehensive maintenance contract": [
#         "comprehensive maintenance contract psa plant",
#         "comprehensive maintenance contract oxygen plant",
#         "comprehensive maintenance contract nitrogen plant",
#         "annual maintenance contract psa plant",
#         "annual maintenance contract oxygen plant",
#         "annual maintenance contract nitrogen plant",
#         "Comprehensive annual maintenance contract of psa oxygen generation plant",
#         "Comprehensive annual maintenance contract psa plant",
#         "Comprehensive annual maintenance contract nitrogen plant",
#         "preventive maintenance oxygen generator",
#         "oxygen plant repair maintenance",
#         "nitrogen plant repair maintenance",
#         "amc psa oxygen plant",
#         "cmc psa oxygen plant",
#         "amc psa nitrogen plant",
#         "cmc psa nitrogen plant",
#         "breakdown maintenance oxygen plant",
#         "breakdown maintenance nitrogen plant",
#         "breakdown maintenance psa plant",
#         "amc psa plany",
#         "cmc psa plant",
#         "customized amc/cmc for pre-owned products - psa plant",
#         "customized amc/cmc for pre-owned products - oxygen psa plant",
#         "customized amc/cmc for pre-owned products - nitrogen psa plant",
#         "customized amc/cmc for pre-owned products - nitrogen gas plant",
#         "customized amc/cmc for pre-owned products - psa oxygen generation plant",
#         "customized amc/cmc for pre-owned products - comprehensive annual maintenance contract of psa oxygen generation plant",
#         "amc tender"
#     ],
#     "Pressure Swing Adsorption plant": [
#         "Pressure Swing Adsorption plant",
#         "Pressure Swing Adsorption oxygen generator",
#         "Pressure Swing Adsorption nitrogen generator",
#     ],
#     "medical oxygen plant": [
#         "medical oxygen plant",
#         "medical oxygen generator",
#         "medical oxygen generation plant",
#         "medical oxygen"
#     ],
#     "industrial oxygen": [
#         "industrial oxygen generator",
#         "industrial nitrogen generator",
#     ],
#     "Molecular sieve oxygen plant": [
#         "Molecular sieve oxygen plant",
#         "Molecular sieve refilling"
#     ],
#     "Zeolite molecular sieve plant": [
#         "Zeolite molecular sieve plant",
#         "Zeolite/sieve replacement"
#     ],
#     "Carbon molecular sieve nitrogen plant": [
#         "Carbon molecular sieve nitrogen plant"
#     ],
#     "camc": [
#         "camc"
#     ],
# }

KEYWORD_CATEGORIES = {
 "oxygen": [
        "oxygen plant",
        "oxygen psa plant",
        "oxygen gas generation",
        "oxygen gas generator",
        "psa oxygen",
        "oxygen generation plant",
        "On-site oxygen generation system",
        "Oxygen concentrator plant",
        "District hospital oxygen plant",
        "Medical college oxygen plant",
    ],
}

# ─── Exclude Keywords ──────────────────────────────────────────────────────

EXCLUDE_KEYWORDS = [
    "oem authorization certificate",
]

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
    """Extract bid ID and build PRODUCTION URL."""
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
    """Extract text from PDF using available library."""
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
    """Check if the exact keyword phrase exists in the text."""
    if not text or not keyword:
        return False
    
    text_lower = text.lower()
    keyword_lower = keyword.lower()
    
    pattern = r'\b' + re.escape(keyword_lower) + r'\b'
    return bool(re.search(pattern, text_lower))

def simple_match(text: str, keyword: str) -> bool:
    """Uses exact phrase matching."""
    return exact_phrase_match(text, keyword)

# ─── Database Functions ──────────────────────────────────────────────────

def load_processed_reference_numbers(client) -> set:
    """
    Load ALL processed reference numbers from processed_references table.
    ONE QUERY at script startup.
    """
    if client is None:
        print("[DB] No Supabase client - cannot load processed references")
        return set()
    
    try:
        print("[DB] Loading processed reference numbers from database...")
        result = client.table("processed_references").select("reference_number").execute()
        
        processed = set()
        for row in (result.data or []):
            ref = row.get("reference_number")
            if ref:
                processed.add(ref)
        
        print(f"[DB] ✅ Loaded {len(processed)} processed reference numbers")
        return processed
        
    except Exception as e:
        print(f"[DB] ⚠️ Failed to load processed references: {e}")
        return set()

def bulk_insert_processed_references(ref_numbers: list, client, batch_size: int = 100) -> int:
    """
    Bulk insert reference numbers into processed_references table.
    """
    if not ref_numbers or not client:
        return 0
    
    # Prepare data for insertion
    rows = [{"reference_number": ref} for ref in ref_numbers]
    total_inserted = 0
    
    for i in range(0, len(rows), batch_size):
        batch = rows[i:i + batch_size]
        try:
            result = client.table("processed_references").insert(batch).execute()
            inserted = len(result.data or [])
            total_inserted += inserted
            print(f"[DB] ✅ Inserted {inserted} reference numbers into processed_references")
        except Exception as e:
            print(f"[DB] ⚠️ Bulk insert into processed_references failed: {e}")
            # Fallback: Try individual inserts
            for row in batch:
                try:
                    client.table("processed_references").insert(row).execute()
                    total_inserted += 1
                except Exception as inner_e:
                    print(f"[DB] ⚠️ Failed to insert reference {row['reference_number']}: {inner_e}")
    
    return total_inserted

def bulk_insert_tenders(tender_list: list, client, batch_size: int = 50) -> int:
    """
    Insert tenders into gem_tenders table in bulk batches.
    """
    if not tender_list or not client:
        return 0
    
    total_inserted = 0
    
    for i in range(0, len(tender_list), batch_size):
        batch = tender_list[i:i + batch_size]
        try:
            result = client.table("gem_tenders").insert(batch).execute()
            inserted = len(result.data or [])
            total_inserted += inserted
            print(f"[DB] ✅ Bulk inserted {inserted} tenders (batch {i//batch_size + 1})")
        except Exception as e:
            print(f"[DB] ⚠️ Bulk insert into gem_tenders failed: {e}")
            # Fallback: Try individual inserts
            for tender in batch:
                try:
                    client.table("gem_tenders").insert(tender).execute()
                    total_inserted += 1
                except Exception as inner_e:
                    print(f"[DB] ⚠️ Failed to insert tender {tender.get('reference_number', 'unknown')}: {inner_e}")
    
    return total_inserted

def prepare_tender_data(raw_data: dict) -> dict:
    """
    Prepare tender data for insertion matching the gem_tenders table schema.
    """
    title = raw_data.get('web_category') or raw_data.get('items', '')
    title = clean_title(title)
    
    if not title or title == 'N/A' or len(title) < 5:
        bid_num = raw_data.get('bid_number', '')
        org = raw_data.get('organization', '')
        title = f"{bid_num} - {org}" if org else bid_num
    
    if not title:
        title = 'Untitled'
    
    bid_number = raw_data.get('bid_number')
    bid_url = raw_data.get('bid_url')
    url_hash = generate_url_hash(bid_url) if bid_url else None
    
    organization = raw_data.get('organization') or raw_data.get('department')
    matched_keyword = raw_data.get('matched_keyword', '')
    matched_category = raw_data.get('matched_category', '')
    
    return {
        "title": title,
        "reference_number": bid_number,
        "organization": organization,
        "location": None,
        "deadline": _normalize_date(raw_data.get('end_date')),
        "estimated_value": None,
        "source_url": bid_url,
        "url_hash": url_hash,
        "keywords_matched": [matched_keyword] if matched_keyword else [],
        "matched_category": matched_category,
        "user_status": "active",
        "scraped_at": datetime.now(timezone.utc).isoformat(),
    }

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
    COMPLETE FLOW - Extract ref number BEFORE PDF download:
    
    1. Load ALL processed references from DB (ONE query)
    2. For each bid:
       a. Extract bid number from HTML (BEFORE PDF download)
       b. Check if in processed_refs (memory lookup - NO DB query)
       c. If exists → SKIP (NO PDF download, NO keyword check)
       d. If new:
          - Download PDF, check keywords
          - ALWAYS add to ref_batch (for processed_references)
          - ONLY if match: add to tender_batch (for gem_tenders)
    3. Bulk insert both tables
    4. Show counter: How many new references added
    """
    
    logger.info("=" * 60)
    logger.info("GeM Tender Scraper - Extract Ref BEFORE PDF Download")
    logger.info(f"Categories: {len(KEYWORD_CATEGORIES)}")
    total_keywords = sum(len(kw) for kw in KEYWORD_CATEGORIES.values())
    logger.info(f"Total Keywords: {total_keywords}")
    logger.info(f"PDF Library: {PDF_LIB_NAME or 'None'}")
    logger.info("=" * 60)
    
    # ─── Initialize Supabase ──────────────────────────────────────────
    client = _get_client()
    
    # ONE QUERY: Load ALL processed references
    processed_refs = load_processed_reference_numbers(client)
    initial_ref_count = len(processed_refs)
    print(f"[INIT] {initial_ref_count} processed reference numbers loaded into memory")
    
    # Track session processing
    processed_in_session = set()
    
    # Batch buffers
    ref_batch = []        # ALL references (matched + unmatched)
    tender_batch = []     # ONLY matched tenders
    REF_BATCH_SIZE = 100
    TENDER_BATCH_SIZE = 50
    
    # Statistics
    total_bids_seen = 0
    total_bids_skipped = 0
    total_new_refs = 0
    total_matches_found = 0
    total_refs_inserted = 0
    total_tenders_inserted = 0
    total_pdfs_downloaded = 0
    
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-blink-features=AutomationControlled"]
        )
        context = await browser.new_context(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/137.0.0.0 Safari/537.36',
            viewport={'width': 1920, 'height': 1080},
            locale='en-IN',
            timezone_id='Asia/Kolkata',
        )
        page = await context.new_page()
        
        try:
            logger.info("Navigating to https://bidplus.gem.gov.in/all-bids ...")
            await page.goto('https://bidplus.gem.gov.in/all-bids', wait_until='domcontentloaded')
            await asyncio.sleep(3)
            
            for category, keywords in KEYWORD_CATEGORIES.items():
                search_term = category
                
                logger.info(f"\n{'='*60}")
                logger.info(f"🎯 PROCESSING CATEGORY: '{category.upper()}'")
                logger.info(f"   Search Term: '{search_term}'")
                logger.info(f"{'='*60}")
                
                # Search
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
                category_seen = 0
                category_skipped = 0
                category_new = 0
                category_matches = 0
                category_pdfs = 0
                
                while True:
                    cards = await page.query_selector_all('#bidCard .card')
                    logger.info(f"  📄 Page {page_num}: Found {len(cards)} bids")
                    
                    for idx, card in enumerate(cards, 1):
                        try:
                            # ─── STEP 1: Extract bid number from HTML ──────────
                            bid_elem = await card.query_selector('a.bid_no_hover')
                            if not bid_elem:
                                continue
                            
                            bid_number = (await bid_elem.text_content() or "").strip()
                            bid_url = await bid_elem.get_attribute('href') or ""
                            
                            total_bids_seen += 1
                            category_seen += 1
                            
                            # ─── STEP 2: Check if already processed ────────────
                            # Using in-memory set - NO DATABASE QUERY!
                            if bid_number and bid_number in processed_refs:
                                logger.info(f"    [{idx}] {bid_number} - ✅ Already processed, skipping (NO PDF download)")
                                category_skipped += 1
                                total_bids_skipped += 1
                                continue
                            
                            if bid_url in processed_in_session:
                                logger.info(f"    [{idx}] {bid_number} - Already in session, skipping")
                                category_skipped += 1
                                total_bids_skipped += 1
                                continue
                            
                            # ─── STEP 3: NEW BID - Process it ──────────────────
                            logger.info(f"    [{idx}] {bid_number} - 🔄 NEW bid, processing...")
                            category_new += 1
                            total_new_refs += 1
                            
                            # Get PDF URL
                            pdf_url = get_pdf_url(bid_url)
                            
                            # Get web category
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
                            
                            # Get organization
                            department = ""
                            organization = ""
                            dept_rows = await card.query_selector_all('.card-body .col-md-5 .row')
                            if len(dept_rows) > 1:
                                dept_text = (await dept_rows[1].text_content() or "").strip()
                                lines = [line.strip() for line in dept_text.split('\n') if line.strip()]
                                department = lines[0] if lines else ""
                                organization = lines[1] if len(lines) > 1 else ""
                            
                            logger.info(f"      📝 Web Category: {web_category[:60]}...")
                            
                            if not pdf_url:
                                logger.info(f"      ⚠️ No valid PDF URL - storing reference anyway")
                                # Still add reference so we don't retry
                                ref_batch.append(bid_number)
                                processed_refs.add(bid_number)
                                processed_in_session.add(bid_url)
                                continue
                            
                            # ─── STEP 4: Download PDF ──────────────────────────
                            logger.info(f"      ⬇️  Downloading PDF...")
                            pdf_text, method = extract_pdf_text(pdf_url)
                            
                            if not pdf_text:
                                logger.info(f"      ❌ PDF extraction failed: {method} - storing reference anyway")
                                # Still add reference so we don't retry
                                ref_batch.append(bid_number)
                                processed_refs.add(bid_number)
                                processed_in_session.add(bid_url)
                                continue
                            
                            category_pdfs += 1
                            total_pdfs_downloaded += 1
                            logger.info(f"      ✅ PDF extracted ({len(pdf_text)} chars)")
                            
                            # ─── STEP 5: Check keywords ─────────────────────────
                            matched_keyword = None
                            for priority_keyword in keywords:
                                if simple_match(pdf_text, priority_keyword):
                                    matched_keyword = priority_keyword
                                    break
                            
                            # ─── STEP 6: Exclude keyword filter ────────────────
                            if matched_keyword:
                                excluded_by = next(
                                    (kw for kw in EXCLUDE_KEYWORDS if simple_match(pdf_text, kw)),
                                    None
                                )
                                if excluded_by:
                                    logger.info(f"      🚫 EXCLUDED! '{matched_keyword}' but found '{excluded_by}'")
                                    matched_keyword = None
                            
                            # ─── STEP 7: ALWAYS add reference ───────────────────
                            ref_batch.append(bid_number)
                            processed_refs.add(bid_number)
                            processed_in_session.add(bid_url)
                            
                            # ─── STEP 8: ONLY if match, add tender ─────────────
                            if matched_keyword:
                                logger.info(f"      ✅ MATCH FOUND! (keyword: '{matched_keyword}')")
                                
                                raw_data = {
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
                                }
                                
                                tender_data = prepare_tender_data(raw_data)
                                tender_batch.append(tender_data)
                                category_matches += 1
                                total_matches_found += 1
                                
                                # Flush tender batch if full
                                if len(tender_batch) >= TENDER_BATCH_SIZE:
                                    print(f"\n[DB] 🔄 Flushing {len(tender_batch)} tenders...")
                                    saved = bulk_insert_tenders(tender_batch, client)
                                    total_tenders_inserted += saved
                                    tender_batch = []
                            else:
                                logger.info(f"      ❌ No match found - reference stored")
                            
                            # ─── STEP 9: Flush reference batch if full ──────────
                            if len(ref_batch) >= REF_BATCH_SIZE:
                                print(f"\n[DB] 🔄 Flushing {len(ref_batch)} references...")
                                saved = bulk_insert_processed_references(ref_batch, client)
                                total_refs_inserted += saved
                                ref_batch = []
                            
                        except Exception as e:
                            logger.error(f"      Error processing bid: {e}")
                            # Still try to store reference if we have bid_number
                            if bid_number:
                                ref_batch.append(bid_number)
                                processed_refs.add(bid_number)
                    
                    # ─── Next page ────────────────────────────────────────────
                    if not await _has_next_page(page):
                        break
                    
                    if not await _go_to_next_page(page):
                        break
                    
                    page_num += 1
                    await asyncio.sleep(1)
                
                logger.info(f"\n  📈 Category '{category.upper()}' summary:")
                logger.info(f"     Total bids seen: {category_seen}")
                logger.info(f"     Bids skipped (already processed): {category_skipped}")
                logger.info(f"     New bids processed: {category_new}")
                logger.info(f"     PDFs downloaded: {category_pdfs}")
                logger.info(f"     Matches found: {category_matches}")
                
                # ─── Flush category remaining ──────────────────────────────────
                if ref_batch:
                    print(f"\n[DB] 🔄 Flushing {len(ref_batch)} remaining references...")
                    saved = bulk_insert_processed_references(ref_batch, client)
                    total_refs_inserted += saved
                    ref_batch = []
                
                if tender_batch:
                    print(f"\n[DB] 🔄 Flushing {len(tender_batch)} remaining tenders...")
                    saved = bulk_insert_tenders(tender_batch, client)
                    total_tenders_inserted += saved
                    tender_batch = []
                
                if list(KEYWORD_CATEGORIES.keys())[-1] != category:
                    await asyncio.sleep(3)
                
        except Exception as e:
            logger.error(f"Scraping error: {e}")
        
        finally:
            # ─── Final flush ──────────────────────────────────────────────────
            if ref_batch:
                print(f"\n[DB] 🔄 Final flush of {len(ref_batch)} references...")
                saved = bulk_insert_processed_references(ref_batch, client)
                total_refs_inserted += saved
                ref_batch = []
            
            if tender_batch:
                print(f"\n[DB] 🔄 Final flush of {len(tender_batch)} tenders...")
                saved = bulk_insert_tenders(tender_batch, client)
                total_tenders_inserted += saved
                tender_batch = []
            
            await context.close()
            await browser.close()
    
    # ─── Final Summary ──────────────────────────────────────────────────────
    
    print(f"\n{'='*70}")
    print(f"[FINAL SUMMARY] Scraping Complete")
    print(f"{'='*70}")
    print(f"📊 BID STATISTICS:")
    print(f"   Total bids seen on pages:     {total_bids_seen}")
    print(f"   Bids skipped (already in DB): {total_bids_skipped}")
    print(f"   New bids processed:           {total_new_refs}")
    print(f"   PDFs downloaded:              {total_pdfs_downloaded}")
    print(f"   Matches found:                {total_matches_found}")
    print(f"{'='*70}")
    print(f"💾 DATABASE INSERTS:")
    print(f"   References inserted into processed_references: {total_refs_inserted}")
    print(f"   Tenders inserted into gem_tenders:            {total_tenders_inserted}")
    print(f"{'='*70}")
    print(f"📈 REFERENCE COUNTER:")
    print(f"   Initial references in DB:  {initial_ref_count}")
    print(f"   New references added:      {total_new_refs}")
    print(f"   Total references now:      {initial_ref_count + total_new_refs}")
    print(f"{'='*70}")
    
    # Archive expired tenders
    archive_client = _get_client()
    archived = archive_expired_gem_tenders(archive_client)
    if archived > 0:
        print(f"[OK] Archived {archived} expired tender(s) from database.")
    
    return total_matches_found

# ─── Main Entry Point ──────────────────────────────────────────────────────

if __name__ == '__main__':
    print("\n" + "=" * 60)
    print("GeM Tender Scraper - Extract Ref BEFORE PDF Download")
    print(f"Categories: {len(KEYWORD_CATEGORIES)}")
    total_keywords = sum(len(kw) for kw in KEYWORD_CATEGORIES.values())
    print(f"Total Keywords: {total_keywords}")
    print(f"Exclude Keywords: {len(EXCLUDE_KEYWORDS)}")
    print("=" * 60 + "\n")
    
    try:
        results = asyncio.run(scrape_gem())
        print(f"\n✅ Done! Found {results} matching tenders.")
    except KeyboardInterrupt:
        print("\n⚠️ Interrupted by user")
    except Exception as e:
        print(f"\n❌ Error: {e}")