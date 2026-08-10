"""
type_c.py
GeM Tender Scraper with Supabase Integration
- Extract ref number BEFORE PDF download
- Store ALL references in processed_references
- Store ONLY matching tenders in gem_tenders
- Bulk insert with proper duplicate checking
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

# ─── Load .env from tenderpulse root ───────────────────────────────────────
try:
    from dotenv import load_dotenv
    _env_path = Path(__file__).parent.parent.parent / ".env"
    load_dotenv(dotenv_path=_env_path, override=True)
    print(f"[ENV] ✅ Loaded .env from {_env_path}")
except Exception as _env_e:
    print(f"[ENV] ⚠️ Could not load .env: {_env_e}")

# ─── Email Digest ──────────────────────────────────────────────────────────
try:
    import importlib.util, os
    _brevo_path = os.path.join(os.path.dirname(__file__), "..", "email", "brevo.py")
    _brevo_path = os.path.abspath(_brevo_path)
    print(f"[EMAIL] Loading brevo from: {_brevo_path}")
    _spec = importlib.util.spec_from_file_location("brevo", _brevo_path)
    _brevo_mod = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(_brevo_mod)
    send_digest = _brevo_mod.send_digest
    _EMAIL_ENABLED = True
    print(f"[EMAIL] ✅ Brevo module loaded successfully")
except Exception as _e:
    print(f"[WARN] Brevo email module not found — digest emails disabled. ({_e})")
    _EMAIL_ENABLED = False
    def send_digest(*args, **kwargs):
        return False

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
#         "psa plant cmc",
#         "operation and maintenance of psa plant",
#         "sitc of psa oxygen plant",
#         "erection and commissioning psa",
#         "supply installation commissioning psa",
#         "design supply installation testing commissioning psa",
#         "retrofitting upgradation of oxygen plant",
#         "refurbishment of psa plant",
#         "compressor overhaul psa plant",
#         "psa plant repair maintenance installation",
#         "camc psa hospital",
#         "sitc oxygen generation plant",
#     ],
#     "oxygen": [
#         "oxygen plant",
#         "oxygen psa plant",
#         "oxygen gas generation",
#         "oxygen gas generator",
#         "psa oxygen",
#          "oxygen gas plant",
#         "oxygen generation plant",
#         "On-site oxygen generation system",
#         "Oxygen concentrator plant",
#         "District hospital oxygen plant",
#         "Medical college oxygen plant",
#         "on-site nitrogen generation system",
#         "nitrogen generation plant",
#         "oxygen generation system for hospital",
#         "replacement of oxygen plant",
#         "oxygen plant comprehensive maintenance",
#     ],
#     "nitrogen": [
#         "nitrogen gas plant",
#         "nitrogen psa plant",
#         "nitrogen gas generation",
#         "nitrogen gas generator",
#         "psa nitrogen",
#         "nitrogen generation plant",
#         "On-site nitrogen generation system",
#         "glass industry nitrogen plant",
#         "pharma industry nitrogen plant",
#         "food packaging nitrogen plant",
#         "nitrogen plant annual maintenance",
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
#         "amc psa plant",
#         "cmc psa plant",
#         "customized amc/cmc for pre-owned products - psa plant",
#         "customized amc/cmc for pre-owned products - oxygen psa plant",
#         "customized amc/cmc for pre-owned products - nitrogen psa plant",
#         "customized amc/cmc for pre-owned products - nitrogen gas plant",
#         "customized amc/cmc for pre-owned products - psa oxygen generation plant",
#         "customized amc/cmc for pre-owned products - comprehensive annual maintenance contract of psa oxygen generation plant",
#         "amc tender",
#         "preventive maintenance contract",
#         "comprehensive amc oxygen plant",
#         "non-comprehensive amc psa plant",
    #     "annual rate contract psa plant",
    #         "annual rate contract oxygen plant",
    #         "annual rate contract nitrogen plant",
    #     "spare parts supply amc",
    #     "warranty and post-warranty maintenance",
    #     "repair and maintenance of plant",
    #     "facility management services oxygen",
    #     "medical oxygen operation and maintenance tender",
    #     "psa oxygen plant amc tender",
    #     "psa nitrogen plant amc tender",
    #     "o&m psa plant",
    # ],
#     "Pressure Swing Adsorption plant": [
#         "Pressure Swing Adsorption plant",
#         "Pressure Swing Adsorption oxygen generator",
#         "Pressure Swing Adsorption nitrogen generator",
#         "zeolite molecular sieve",
#     ],
#     "medical oxygen plant": [
#         "medical oxygen plant",
#         "medical oxygen generator",
#         "medical oxygen generation plant",
#         "medical oxygen generation system",
#         "medical gas pipeline system",
#         "oxygen generation system for hospital",
#         "liquid medical oxygen",
#     ],
#     "industrial oxygen": [
#         "industrial oxygen generator",
#         "industrial nitrogen generator",
#         "psu industrial oxygen plant",
#         "steel plant oxygen plant",
#         "industrial oxygen plant",
#         "industrial nitrogen plant",
#         # // we can add industrial oxygen plant and industrial nitrogen plant as well
#     ],
#     "Molecular sieve oxygen plant": [
#         "Molecular sieve oxygen plant",
#         "Molecular sieve refilling",
#         "zeolite molecular sieve plant",
#         "zeolite sieve replacement",
#         "air dryer maintenance",
#     ],
#     "Zeolite molecular sieve plant": [
#         "Zeolite molecular sieve plant",
#         "Zeolite/sieve replacement",
#         "Carbon molecular sieve nitrogen plant",
#     ],
#     "Carbon molecular sieve nitrogen plant": [
#         "Carbon molecular sieve nitrogen plant",
#     ],
#     "camc": [
#         "camc oxygen plant",
#         "camc nitrogen plant",
#         "Comprehensive Annual Maintenance Contract psa plant",
#     ],
#     "government hospital": [
#         "government hospital psa plant",
#         "health department oxygen tender",
#         "national health mission oxygen plant",
#         "state medical services corporation",
#         "cghs oxygen plant",
#         "esic hospital oxygen plant",
#         "railway hospital oxygen plant",
#         "defence hospital oxygen plant",
#         "pm cares oxygen plant",
#     ],
#     "sitc": [
#         "turnkey supply installation testing commissioning",
#         "sitc of psa oxygen plant",
#         "sitc oxygen generation plant",
#         "design supply installation testing commissioning psa",
#         "erection and commissioning psa",
#         "supply installation commissioning psa",
#     ],
# }

KEYWORD_CATEGORIES = {
    "psa": [
        "psa plant",
        "psa nitrogen plant",
        "psa oxygen plant",
        "psa amc",
        "psa cmc",
        "psa plant cmc",
        "operation and maintenance of psa plant",
        "sitc of psa oxygen plant",
        "erection and commissioning psa",
        "supply installation commissioning psa",
        "design supply installation testing commissioning psa",
        "retrofitting upgradation of oxygen plant",
        "refurbishment of psa plant",
        "compressor overhaul psa plant",
        "psa plant repair maintenance installation",
        "camc psa hospital",
        "sitc oxygen generation plant",
    ],
}

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
    if not text:
        return False
    return bool(re.search(r'[\u0900-\u097F]', text))

def extract_english_text(text: str) -> str:
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

# ─── Exact Phrase Matching ─────────────────────────────────────────────

def exact_phrase_match(text: str, keyword: str) -> bool:
    if not text or not keyword:
        return False
    
    text_lower = text.lower()
    keyword_lower = keyword.lower()
    
    pattern = r'\b' + re.escape(keyword_lower) + r'\b'
    return bool(re.search(pattern, text_lower))

def simple_match(text: str, keyword: str) -> bool:
    return exact_phrase_match(text, keyword)

# ─── Database Functions ──────────────────────────────────────────────────

def load_processed_reference_numbers(client) -> set:
    if client is None:
        print("[DB] No Supabase client - cannot load processed references")
        return set()

    try:
        print("[DB] Loading processed reference numbers from database...")
        processed = set()
        page_size = 1000
        offset = 0

        while True:
            result = client.table("processed_references") \
                .select("reference_number") \
                .range(offset, offset + page_size - 1) \
                .execute()

            rows = result.data or []
            for row in rows:
                ref = row.get("reference_number")
                if ref:
                    processed.add(ref)

            print(f"[DB]   ... fetched {offset + len(rows)} processed references so far")

            if len(rows) < page_size:
                break  # reached last page
            offset += page_size

        print(f"[DB] ✅ Loaded {len(processed)} processed reference numbers (all pages)")
        return processed

    except Exception as e:
        print(f"[DB] ⚠️ Failed to load processed references: {e}")
        return set()

def load_gem_tender_references(client) -> set:
    """Load all reference_numbers already in gem_tenders into memory at startup."""
    if client is None:
        print("[DB] No Supabase client - cannot load gem_tender references")
        return set()

    try:
        print("[DB] Loading gem_tenders reference numbers from database...")
        gem_refs = set()
        page_size = 1000
        offset = 0

        while True:
            result = client.table("gem_tenders") \
                .select("reference_number") \
                .range(offset, offset + page_size - 1) \
                .execute()

            rows = result.data or []
            for row in rows:
                ref = row.get("reference_number")
                if ref:
                    gem_refs.add(ref)

            print(f"[DB]   ... fetched {offset + len(rows)} gem_tenders references so far")

            if len(rows) < page_size:
                break  # reached last page
            offset += page_size

        print(f"[DB] ✅ Loaded {len(gem_refs)} gem_tenders reference numbers (all pages)")
        return gem_refs

    except Exception as e:
        print(f"[DB] ⚠️ Failed to load gem_tenders references: {e}")
        return set()


def bulk_insert_processed_references(ref_numbers: list, client, existing_refs: set, batch_size: int = 100) -> int:
    """
    Insert ONLY NEW references into processed_references table.
    Returns: number of references actually inserted
    """
    if not ref_numbers or not client:
        return 0
    
    # Filter: Only keep references NOT already in DB
    new_refs = [ref for ref in ref_numbers if ref not in existing_refs]
    
    if not new_refs:
        print(f"[DB] ℹ️ All {len(ref_numbers)} references already exist - nothing to insert")
        return 0
    
    print(f"[DB] 📊 {len(new_refs)} NEW references out of {len(ref_numbers)} total")
    
    # Prepare data for insertion
    rows = [{"reference_number": ref} for ref in new_refs]
    total_inserted = 0
    
    for i in range(0, len(rows), batch_size):
        batch = rows[i:i + batch_size]
        try:
            result = client.table("processed_references").upsert(batch, on_conflict="reference_number").execute()
            inserted = len(result.data or [])
            total_inserted += inserted
            
            # Update the in-memory set with inserted references
            for row in result.data or []:
                if row.get("reference_number"):
                    existing_refs.add(row.get("reference_number"))
            
            print(f"[DB] ✅ Inserted {inserted} NEW reference numbers")
        except Exception as e:
            print(f"[DB] ⚠️ Bulk insert failed: {e}")
            # Fallback: Try individual inserts
            for row in batch:
                try:
                    result = client.table("processed_references").upsert(row, on_conflict="reference_number").execute()
                    if result.data and len(result.data) > 0:
                        total_inserted += 1
                        if row.get("reference_number"):
                            existing_refs.add(row.get("reference_number"))
                except Exception as inner_e:
                    print(f"[DB] ⚠️ Failed to insert {row['reference_number']}: {inner_e}")
    
    return total_inserted

def bulk_insert_tenders(tender_list: list, client, gem_refs: set, batch_size: int = 50) -> int:
    """
    Insert ONLY NEW tenders into gem_tenders table.
    Deduplication uses the in-memory gem_refs set (loaded once at startup).
    gem_refs is updated in-place after each successful insert — no per-batch DB queries.
    Returns: number of tenders actually inserted
    """
    if not tender_list or not client:
        return 0

    # Filter using in-memory set — O(1) per lookup, zero extra DB calls
    new_tenders = [t for t in tender_list if t.get('reference_number') not in gem_refs]

    if not new_tenders:
        print(f"[DB] ℹ️ All {len(tender_list)} tenders already in gem_tenders (in-memory check) - nothing to insert")
        return 0

    print(f"[DB] 📊 {len(new_tenders)} NEW tenders out of {len(tender_list)} total (skipping {len(tender_list) - len(new_tenders)} already in gem_tenders)")
    
    total_inserted = 0

    for i in range(0, len(new_tenders), batch_size):
        batch = new_tenders[i:i + batch_size]
        try:
            result = client.table("gem_tenders").insert(batch).execute()
            inserted = len(result.data or [])
            total_inserted += inserted
            # Update in-memory set so subsequent batches stay consistent
            for row in (result.data or []):
                if row.get("reference_number"):
                    gem_refs.add(row["reference_number"])
            print(f"[DB] ✅ Bulk inserted {inserted} NEW tenders into gem_tenders")
        except Exception as e:
            print(f"[DB] ⚠️ Bulk insert failed: {e}")
            for tender in batch:
                try:
                    result = client.table("gem_tenders").insert(tender).execute()
                    total_inserted += 1
                    # Update in-memory set on individual insert too
                    ref = tender.get('reference_number')
                    if ref:
                        gem_refs.add(ref)
                except Exception as inner_e:
                    print(f"[DB] ⚠️ Failed to insert {tender.get('reference_number')}: {inner_e}")

    return total_inserted


def bulk_insert_today_tenders(tender_list: list, client, existing_refs: set, batch_size: int = 50) -> int:
    """
    Insert NEW tenders into today_gem_tenders for the current scrape day.
    - existing_refs: the same processed_refs set used for gem_tenders deduplication.
    - Only inserts tenders whose reference_number is NOT already in today_gem_tenders
      (checked via a fresh DB query for today's records).
    - Uses upsert (on_conflict='reference_number') so duplicate runs are safe.
    """
    if not tender_list or not client:
        return 0

    allowed_keys = {
        "title",
        "reference_number",
        "organization",
        "location",
        "deadline",
        "estimated_value",
        "source_url",
        "url_hash",
        "keywords_matched",
        "user_status",
        "scraped_at",
    }

    # Fetch reference numbers already in today_gem_tenders to avoid duplicates
    try:
        today_start = datetime.now(timezone.utc).replace(
            hour=0, minute=0, second=0, microsecond=0
        ).isoformat()
        existing_today_res = client.table("today_gem_tenders") \
            .select("reference_number") \
            .gte("scraped_at", today_start) \
            .execute()
        today_refs = {
            row["reference_number"]
            for row in (existing_today_res.data or [])
            if row.get("reference_number")
        }
    except Exception as e:
        print(f"[DB] ⚠️ Could not load today_gem_tenders refs: {e}")
        today_refs = set()

    # Only insert tenders not already in today_gem_tenders
    new_tenders = [
        t for t in tender_list
        if t.get("reference_number") not in today_refs
    ]

    if not new_tenders:
        print(f"[DB] ℹ️ All {len(tender_list)} tenders already in today_gem_tenders — skipping")
        return 0

    print(f"[DB] 📊 Inserting {len(new_tenders)} NEW tenders into today_gem_tenders (skipping {len(tender_list) - len(new_tenders)} duplicates)")

    total_inserted = 0
    for i in range(0, len(new_tenders), batch_size):
        batch = new_tenders[i:i + batch_size]
        safe_batch = [
            {k: v for k, v in tender.items() if k in allowed_keys}
            for tender in batch
        ]
        try:
            result = client.table("today_gem_tenders").upsert(
                safe_batch, on_conflict="reference_number"
            ).execute()
            inserted = len(result.data or [])
            total_inserted += inserted
            print(f"[DB] ✅ Upserted {inserted} tenders into today_gem_tenders")
        except Exception as e:
            print(f"[DB] ⚠️ Bulk upsert into today_gem_tenders failed: {e}")
            for tender in safe_batch:
                try:
                    client.table("today_gem_tenders").upsert(
                        tender, on_conflict="reference_number"
                    ).execute()
                    total_inserted += 1
                except Exception as inner_e:
                    lower = str(inner_e).lower()
                    if "duplicate" in lower or "unique" in lower or "already exists" in lower:
                        continue
                    print(f"[DB] ⚠️ Failed to upsert today tender {tender.get('reference_number')}: {inner_e}")

    return total_inserted


def clear_old_today_gem_tenders(client):
    if client is None:
        print("[TODAY CLEANUP] No Supabase client — skipping today_gem_tenders cleanup.")
        return 0

    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
    print(f"[TODAY CLEANUP] Removing today_gem_tenders scraped before {today_start}...")

    try:
        result = client.table("today_gem_tenders") \
            .delete() \
            .lt("scraped_at", today_start) \
            .execute()
        deleted = len(result.data or [])
        print(f"[TODAY CLEANUP] Removed {deleted} old today_gem_tenders row(s)")
        return deleted
    except Exception as e:
        print(f"[TODAY CLEANUP] Failed to remove old rows: {e}")
        return 0


def prepare_tender_data(raw_data: dict) -> dict:
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
    # Ensure full URL — stored href is sometimes a relative path like /showbidDocument/123
    # get_pdf_url() always returns https://bidplus.gem.gov.in/showbidDocument/<id>
    bid_url = get_pdf_url(bid_url) if bid_url else bid_url
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

            # Hard-delete from gem_tenders so the UI only shows active tenders
            client.table("gem_tenders") \
                .delete() \
                .eq("id", tender_id) \
                .execute()

            archived_count += 1
            print(f"   [OK] Archived & removed from gem_tenders: {tender.get('title', tender_id)[:60]}")

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
    # ─── Startup keyword summary printed FIRST before anything else ───
    _total_kw = sum(len(kws) for kws in KEYWORD_CATEGORIES.values())
    print(f"\n{'='*60}")
    print(f"[KEYWORD SUMMARY] {len(KEYWORD_CATEGORIES)} categories | {_total_kw} total keywords | PDF lib: {PDF_LIB_NAME or 'None'}")
    print(f"{'='*60}")
    for cat_name, cat_keywords in KEYWORD_CATEGORIES.items():
        print(f"  📂 [{cat_name}] — {len(cat_keywords)} keywords:")
        for kw in cat_keywords:
            print(f"       • {kw}")
    print(f"{'='*60}")
    print(f"  🔍 Every PDF searched against ALL {_total_kw} keywords across all categories")
    print(f"  🚫 Exclude keywords: {len(EXCLUDE_KEYWORDS)}")
    for kw in EXCLUDE_KEYWORDS:
        print(f"       • {kw}")
    print(f"{'='*60}\n")

    # ─── Initialize Supabase ──────────────────────────────────────────
    client = _get_client()
    
    if client is None:
        print("[ERROR] ❌ No Supabase client available!")
        return []

    # Ensure only today's tenders remain in the today_gem_tenders table
    clear_old_today_gem_tenders(client)
    
    # ONE QUERY: Load ALL processed references (tracks all scraped PDFs)
    processed_refs = load_processed_reference_numbers(client)
    initial_ref_count = len(processed_refs)
    print(f"[INIT] {initial_ref_count} processed reference numbers loaded into memory")

    # ONE QUERY: Load ALL gem_tenders reference numbers (used for tender insert dedup)
    gem_refs = load_gem_tender_references(client)
    print(f"[INIT] {len(gem_refs)} gem_tenders reference numbers loaded into memory")
    
    # Track bids processed in this session
    processed_in_session = set()
    all_results = []
    pending_email = []     # matches collected for email — survives Ctrl+C via finally
    
    # Batch buffers
    ref_batch = []        # ALL new references (to be inserted)
    REF_BATCH_SIZE = 100
    
    # Statistics - ACCURATE counting
    total_bids_seen = 0
    total_bids_skipped = 0
    total_new_refs_found = 0
    total_refs_inserted = 0
    total_matches_found = 0
    total_tenders_inserted = 0
    total_pdfs_downloaded = 0
    total_today_inserted = 0
    
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
            
            for category, keywords in KEYWORD_CATEGORIES.items():
                search_term = category
                
                logger.info(f"\n{'='*60}")
                logger.info(f"🎯 PROCESSING CATEGORY: '{category.upper()}'")
                logger.info(f"   Search Term: '{search_term}'")
                logger.info(f"   Keywords: {len(keywords)} keywords")
                logger.info(f"{'='*60}")
                
                # ─── Search ──────────────────────────────────────────────
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
                            # ─── STEP 1: Extract bid number (BEFORE PDF) ───
                            bid_elem = await card.query_selector('a.bid_no_hover')
                            if not bid_elem:
                                continue
                            
                            bid_number = (await bid_elem.text_content() or "").strip()
                            bid_url = await bid_elem.get_attribute('href') or ""
                            
                            total_bids_seen += 1
                            category_seen += 1
                            
                            # ─── STEP 2: Check if already processed ────────
                            if bid_number and bid_number in processed_refs:
                                logger.info(f"    [{idx}] {bid_number} - ✅ Already processed, skipping (NO PDF)")
                                category_skipped += 1
                                total_bids_skipped += 1
                                continue
                            
                            if bid_url in processed_in_session:
                                logger.info(f"    [{idx}] {bid_number} - Already in session, skipping")
                                category_skipped += 1
                                total_bids_skipped += 1
                                continue
                            
                            # ─── STEP 3: NEW BID - Process it ──────────────
                            logger.info(f"    [{idx}] {bid_number} - 🔄 NEW bid, processing...")
                            category_new += 1
                            total_new_refs_found += 1
                            
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
                                logger.info(f"      ⚠️ No valid PDF URL - will store reference")
                                ref_batch.append(bid_number)
                                processed_in_session.add(bid_url)
                                continue
                            
                            # ─── STEP 4: Download PDF ──────────────────────
                            logger.info(f"      ⬇️  Downloading PDF...")
                            pdf_text, method = extract_pdf_text(pdf_url)
                            
                            if not pdf_text:
                                logger.info(f"      ❌ PDF extraction failed: {method} - will store reference")
                                ref_batch.append(bid_number)
                                processed_in_session.add(bid_url)
                                continue
                            
                            category_pdfs += 1
                            total_pdfs_downloaded += 1
                            logger.info(f"      ✅ PDF extracted ({len(pdf_text)} chars)")
                            
                            # ─── STEP 5: Check ALL keywords from ALL categories ──
                            # Search every category's keywords so one PDF download
                            # covers all possible matches — ref is then safe to index.
                            matched_keyword = None
                            matched_category_name = None
                            for cat_name, cat_keywords in KEYWORD_CATEGORIES.items():
                                for kw in cat_keywords:
                                    if simple_match(pdf_text, kw):
                                        matched_keyword = kw
                                        matched_category_name = cat_name
                                        break
                                if matched_keyword:
                                    break
                            
                            # ─── STEP 6: Exclude keyword filter ────────────
                            if matched_keyword:
                                excluded_by = next(
                                    (kw for kw in EXCLUDE_KEYWORDS if simple_match(pdf_text, kw)),
                                    None
                                )
                                if excluded_by:
                                    logger.info(f"      🚫 EXCLUDED! '{matched_keyword}' but found '{excluded_by}'")
                                    matched_keyword = None
                                    matched_category_name = None
                            
                            # ─── STEP 7: ALWAYS add reference ──────────────
                            ref_batch.append(bid_number)
                            processed_in_session.add(bid_url)
                            
                            # ─── STEP 8: ONLY if match, add tender ─────────
                            if matched_keyword:
                                logger.info(f"      ✅ MATCH FOUND! (keyword: '{matched_keyword}' | category: '{matched_category_name}')")
                                
                                raw_data = {
                                    'bid_number': bid_number,
                                    'bid_url': bid_url,
                                    'pdf_url': pdf_url,
                                    'web_category': web_category,
                                    'items': web_category,
                                    'matched_keyword': matched_keyword,
                                    'matched_category': matched_category_name,
                                    'department': department,
                                    'organization': organization,
                                    'end_date': end_date.strip() if end_date else "",
                                    'scraped_at': datetime.now().isoformat()
                                }
                                
                                tender_data = prepare_tender_data(raw_data)
                                
                                # Insert immediately — safe even if closed mid-run
                                inserted = bulk_insert_tenders([tender_data], client, gem_refs)
                                total_tenders_inserted += inserted
                                today_inserted = bulk_insert_today_tenders([tender_data], client, processed_refs)
                                total_today_inserted += today_inserted
                                
                                all_results.append(raw_data)
                                pending_email.append(raw_data)  # collected for final email
                                category_matches += 1
                                total_matches_found += 1
                            else:
                                logger.info(f"      ❌ No match found - reference will be stored")
                            
                            # ─── STEP 9: Flush reference batch if full ────
                            if len(ref_batch) >= REF_BATCH_SIZE:
                                print(f"\n[DB] 🔄 Flushing {len(ref_batch)} references...")
                                inserted = bulk_insert_processed_references(ref_batch, client, processed_refs)
                                total_refs_inserted += inserted
                                ref_batch = []
                            
                        except Exception as e:
                            logger.error(f"      Error processing bid: {e}")
                            # Still try to store reference
                            if 'bid_number' in locals() and bid_number:
                                ref_batch.append(bid_number)
                    
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
                
                # ─── Flush category remaining ──────────────────────────────
                if ref_batch:
                    print(f"\n[DB] 🔄 Flushing {len(ref_batch)} remaining references...")
                    inserted = bulk_insert_processed_references(ref_batch, client, processed_refs)
                    total_refs_inserted += inserted
                    ref_batch = []
                
                if list(KEYWORD_CATEGORIES.keys())[-1] != category:
                    logger.info(f"\n⏳ Waiting 3 seconds before next category...")
                    await asyncio.sleep(3)
                
        except Exception as e:
            logger.error(f"Scraping error: {e}")
        
        finally:
            # ─── Final flush ──────────────────────────────────────────────────
            if ref_batch:
                print(f"\n[DB] 🔄 Final flush of {len(ref_batch)} references...")
                inserted = bulk_insert_processed_references(ref_batch, client, processed_refs)
                total_refs_inserted += inserted
                ref_batch = []
            
            # ─── Email on exit (Ctrl+C or normal completion) ─────────
            if _EMAIL_ENABLED:
                if pending_email:
                    print(f"\n[EMAIL] 📧 Sending digest for {len(pending_email)} tender(s)...")
                    email_tenders = []
                    for raw in pending_email:
                        title = clean_title(raw.get("web_category") or raw.get("items") or "")
                        bid_url = get_pdf_url(raw.get("bid_url", ""))  # ensure full bidplus.gem.gov.in URL
                        email_tenders.append({
                            "title":            title or raw.get("bid_number", "Untitled"),
                            "reference_number": raw.get("bid_number"),
                            "organization":     raw.get("organization") or raw.get("department"),
                            "location":         None,
                            "deadline":         _normalize_date(raw.get("end_date")),
                            "estimated_value":  None,
                            "source_url":       bid_url,
                            "source_site":      "GeM",
                            "url_hash":         generate_url_hash(bid_url) if bid_url else None,
                            "keywords_matched": [raw["matched_keyword"]] if raw.get("matched_keyword") else [],
                            "document_urls":    [raw["pdf_url"]] if raw.get("pdf_url") else [],
                        })
                    sent = send_digest(email_tenders)
                    if sent:
                        print("[EMAIL] ✅ Digest sent successfully.")
                    else:
                        print("[EMAIL] ⚠️  Digest NOT sent — check Brevo logs.")
                else:
                    print("\n[EMAIL] ℹ️  No matches found — digest skipped.")
            else:
                print("\n[EMAIL] ⚠️  Email disabled (brevo module not loaded).")

            await context.close()
            await browser.close()
    
    # ─── Final Summary ──────────────────────────────────────────────────────
    
    print(f"\n{'='*70}")
    print(f"[FINAL SUMMARY] Scraping Complete")
    print(f"{'='*70}")
    print(f"📊 BID STATISTICS:")
    print(f"   Total bids seen on pages:     {total_bids_seen}")
    print(f"   Bids skipped (already in DB): {total_bids_skipped}")
    print(f"   New bids found (not in DB):   {total_new_refs_found}")
    print(f"   PDFs downloaded:              {total_pdfs_downloaded}")
    print(f"   Matches found:                {total_matches_found}")
    print(f"{'='*70}")
    print(f"💾 DATABASE INSERTS:")
    print(f"   References inserted into processed_references: {total_refs_inserted}")
    print(f"   Tenders inserted into gem_tenders:            {total_tenders_inserted}")
    print(f"   Tenders inserted into today_gem_tenders:      {total_today_inserted}")
    print(f"{'='*70}")
    print(f"📈 REFERENCE COUNTER:")
    print(f"   Initial references in DB:  {initial_ref_count}")
    print(f"   New references inserted:   {total_refs_inserted}")
    print(f"   Total references now:      {initial_ref_count + total_refs_inserted}")
    print(f"{'='*70}")
    
    # Archive expired tenders
    archive_client = _get_client()
    archived = archive_expired_gem_tenders(archive_client)
    if archived > 0:
        print(f"[OK] Archived {archived} expired tender(s) from database.")
    
    # Print sample of matches
    if all_results:
        print("\n[Sample of matches:]")
        for i, item in enumerate(all_results[:5], 1):
            title = safe_get_string(item.get('web_category', item.get('items')), 'Untitled')
            title = clean_title(title)
            ref = safe_get_string(item.get('bid_number'), 'No Ref')
            keyword = safe_get_string(item.get('matched_keyword'), 'Unknown')
            category = safe_get_string(item.get('matched_category'), 'Unknown')
            print(f"  {i}. {title[:60]} - {ref}")
            print(f"     Category: {category} | Matched: '{keyword}'")
        
        if len(all_results) > 5:
            print(f"  ... and {len(all_results) - 5} more")

    # Email is now sent in the finally block above — works on Ctrl+C too

    return all_results

# ─── Main Entry Point ──────────────────────────────────────────────────────

if __name__ == '__main__':
    print("\n" + "=" * 60)
    print("GeM Tender Scraper - Reference Tracking & Bulk Insert")
    print(f"Categories: {len(KEYWORD_CATEGORIES)}")
    total_keywords = sum(len(kw) for kw in KEYWORD_CATEGORIES.values())
    print(f"Total Keywords: {total_keywords}")
    print(f"Exclude Keywords: {len(EXCLUDE_KEYWORDS)}")
    print("=" * 60 + "\n")
    
    try:
        results = asyncio.run(scrape_gem())
        print(f"\n✅ Done! Found {len(results)} matching tenders.")
    except KeyboardInterrupt:
        print("\n⚠️ Interrupted by user")
    except Exception as e:
        print(f"\n❌ Error: {e}")