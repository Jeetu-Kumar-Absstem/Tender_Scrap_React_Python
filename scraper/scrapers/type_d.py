# scraper/scrapers/type_d.py
import time
import csv
import re
import hashlib
import os
import sys
from datetime import datetime, timezone
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, StaleElementReferenceException, ElementNotInteractableException
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup

# Fix Windows console encoding issues
if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except AttributeError:
        import codecs
        sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'replace')

# --- Try to import from schema, with fallback ---
try:
    from scraper.core.schema import INCLUDE_KEYWORDS
    from scraper.core.supabase_store import _get_client
    print(f"[INIT] Successfully imported from scraper.core")
except ImportError as e:
    print(f"[WARN] Could not import from scraper.core: {e}")
    # Fallback keywords
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
            import os
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

# --- Configuration ---
BASE_URL = "https://tender18.com/"
WAIT_TIME = 10
PAGE_LOAD_DELAY = 2
MAX_PAGES = 3  # Number of pages to scrape per keyword

# Use keywords from schema - filter for PSA related
KEYWORDS = [kw for kw in INCLUDE_KEYWORDS if any(
    term in kw.lower() for term in ['psa', 'oxygen', 'nitrogen', 'medical', 'gas', 'o2', 'vpsa', 'lox']
)]

if not KEYWORDS:
    KEYWORDS = ["psa plant", "oxygen psa plant", "medical oxygen generation plant"]
    print("[WARN] No matching keywords found, using fallback")

print(f"[INIT] Setting up WebDriver...")
print(f"[INIT] Total keywords for scraping: {len(KEYWORDS)}")
print(f"[INIT] Max pages per keyword: {MAX_PAGES}")

# --- Setup Selenium Driver (Headless Mode) ---
try:
    service = Service(ChromeDriverManager().install())
    options = webdriver.ChromeOptions()
    
    # Headless configuration for production
    options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-gpu')
    options.add_argument('--window-size=1920,1080')
    options.add_argument('--disable-blink-features=AutomationControlled')
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)
    
    # Add user agent to avoid detection
    options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
    
    driver = webdriver.Chrome(service=service, options=options)
    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    print("[OK] Headless WebDriver initialized successfully.")
except Exception as e:
    print(f"[ERROR] Failed to setup WebDriver: {e}")
    sys.exit(1)

# --- Helper Functions ---
def safe_get_string(value, default="Untitled"):
    """Safely get a string value, handling None."""
    if value is None:
        return default
    return str(value)

def parse_tender_card(card, keyword):
    """Extracts tender information from a BeautifulSoup 'live-tenders-block' element."""
    try:
        ref_no_element = card.select_one('.tenders-top-left h6 span')
        ref_no = ref_no_element.text.strip() if ref_no_element else None
    except:
        ref_no = None

    try:
        location_span = card.select_one('.location h6 span')
        if location_span:
            location_links = location_span.find_all('a')
            location = ', '.join([link.text.strip() for link in location_links]) if location_links else location_span.text.strip()
        else:
            location = None
    except:
        location = None

    # Better title extraction
    try:
        title_element = card.select_one('.tender-work h4 a span')
        if not title_element:
            title_element = card.select_one('.tender-work h4 a')
        if not title_element:
            title_element = card.select_one('.tender-work h4')
        if not title_element:
            title_element = card.select_one('.tender-title')
        if not title_element:
            title_element = card.select_one('h4')
        
        if title_element:
            title = title_element.text.strip()
        else:
            title = None
    except:
        title = None

    # If title is None, try to get from ref_no
    if not title and ref_no:
        title = f"Tender {ref_no}"

    try:
        agency_element = card.select_one('.tender-bottom-flex .tenders-top-left h6 span a')
        agency = agency_element.text.strip() if agency_element else None
    except:
        agency = None

    # Tender Value - Set to "Refer to Document" if not available
    try:
        tender_value_element = card.select_one('.tender-bottom-flex .tenders-top-right h6 span')
        if tender_value_element:
            tender_value = tender_value_element.text.strip()
            if not tender_value or tender_value == "N/A" or tender_value == "0" or tender_value == "0.00" or tender_value == "₹0":
                tender_value = "Refer to Document"
        else:
            tender_value = "Refer to Document"
    except:
        tender_value = "Refer to Document"

    try:
        due_date_element = card.select_one('.due-date h6 span')
        due_date = due_date_element.text.strip() if due_date_element else None
    except:
        due_date = None

    try:
        detail_url_element = card.select_one('.tender-work h4 a')
        if detail_url_element:
            detail_url = detail_url_element['href']
            if detail_url.startswith('/'):
                detail_url = BASE_URL[:-1] + detail_url
        else:
            detail_url = None
    except:
        detail_url = None

    return {
        'ref_no': ref_no,
        'title': title,
        'location': location,
        'agency': agency,
        'tender_value': tender_value,
        'due_date': due_date,
        'detail_url': detail_url,
        'keyword': keyword
    }

def scrape_current_page(keyword, page_num=1):
    """Scrapes the currently loaded page for tender results."""
    time.sleep(2)
    page_source = driver.page_source
    soup = BeautifulSoup(page_source, 'html.parser')
    
    tender_blocks = soup.select('div.live-tenders-block')
    
    if not tender_blocks:
        print(f"   [WARN] No tender blocks found on page {page_num} for keyword '{keyword}'.")
        no_results = soup.find(string=re.compile(r'No results found|no tender', re.I))
        if no_results:
            print(f"   [INFO] No results found for keyword '{keyword}'.")
        return []
    
    results = []
    for card in tender_blocks:
        tender_data = parse_tender_card(card, keyword)
        if tender_data['title'] or tender_data['ref_no']:
            results.append(tender_data)
        else:
            print(f"   [WARN] Skipping card with no title or ref number")
    
    return results

def go_to_next_page():
    """
    Enhanced pagination handler that works with various pagination structures.
    Specifically handles the ul > li > button structure identified on tender18.com.
    """
    try:
        # Try multiple strategies for finding next button
        
        # Strategy 1: Look for button with text "Next" or "›"
        try:
            next_buttons = driver.find_elements(By.XPATH, 
                "//button[contains(text(), 'Next') or contains(text(), '›') or contains(text(), '»')]")
            
            for btn in next_buttons:
                # Check if button or parent has disabled class
                parent = btn.find_element(By.XPATH, "./..")
                parent_class = parent.get_attribute("class") or ""
                
                if "disabled" not in parent_class and "disabled" not in (btn.get_attribute("class") or ""):
                    if btn.is_enabled():
                        # Scroll to button
                        driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", btn)
                        time.sleep(0.5)
                        # Click using JavaScript
                        driver.execute_script("arguments[0].click();", btn)
                        return True
        except:
            pass
        
        # Strategy 2: Look for li with class page-item containing Next
        try:
            next_items = driver.find_elements(By.XPATH, 
                "//li[contains(@class, 'page-item')]//button[contains(text(), 'Next') or contains(text(), '›')]")
            
            for item in next_items:
                parent_li = item.find_element(By.XPATH, "./..")
                parent_class = parent_li.get_attribute("class") or ""
                
                if "disabled" not in parent_class and item.is_enabled():
                    driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", item)
                    time.sleep(0.5)
                    driver.execute_script("arguments[0].click();", item)
                    return True
        except:
            pass
        
        # Strategy 3: Look for any pagination link with next text
        try:
            pagination = driver.find_element(By.CSS_SELECTOR, ".pagination, .page-numbers, nav[aria-label*='pagination']")
            links = pagination.find_elements(By.TAG_NAME, "a")
            
            for link in links:
                text = link.text.strip().lower()
                if "next" in text or "»" in text or "›" in text or "→" in text:
                    if link.is_enabled() and "disabled" not in (link.get_attribute("class") or ""):
                        driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", link)
                        time.sleep(0.5)
                        driver.execute_script("arguments[0].click();", link)
                        return True
        except:
            pass
        
        # Strategy 4: Look for aria-label="Next" on any element
        try:
            next_btn = driver.find_element(By.CSS_SELECTOR, "[aria-label='Next'], [aria-label='Next Page']")
            if next_btn.is_enabled() and "disabled" not in (next_btn.get_attribute("class") or ""):
                driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", next_btn)
                time.sleep(0.5)
                driver.execute_script("arguments[0].click();", next_btn)
                return True
        except:
            pass
        
        # Strategy 5: Fallback - try to find the next page number
        try:
            # Find all page numbers
            page_links = driver.find_elements(By.CSS_SELECTOR, 
                ".page-item a, .page-link, .pagination a, .page-numbers:not(.dots)")
            
            current_page = None
            for link in page_links:
                if "active" in (link.get_attribute("class") or ""):
                    try:
                        current_page = int(link.text.strip())
                    except:
                        pass
                    break
            
            if current_page:
                next_page_num = current_page + 1
                for link in page_links:
                    try:
                        if int(link.text.strip()) == next_page_num:
                            driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", link)
                            time.sleep(0.5)
                            driver.execute_script("arguments[0].click();", link)
                            return True
                    except:
                        continue
        except:
            pass
        
        return False
        
    except Exception as e:
        print(f"   [WARN] Could not go to next page: {e}")
        return False

def is_last_page():
    """Check if current page is the last page."""
    try:
        # Check if Next button is disabled
        next_buttons = driver.find_elements(By.XPATH, 
            "//button[contains(text(), 'Next') or contains(text(), '›')]")
        
        for btn in next_buttons:
            parent = btn.find_element(By.XPATH, "./..")
            parent_class = parent.get_attribute("class") or ""
            btn_class = btn.get_attribute("class") or ""
            
            if "disabled" in parent_class or "disabled" in btn_class:
                return True
        
        # Check for last page indicators
        last_elements = driver.find_elements(By.XPATH, 
            "//*[contains(text(), 'Last Page') or contains(text(), 'No more pages')]")
        if last_elements:
            return True
        
        return False
    except:
        return False

def wait_for_results():
    """Waits for search results to load after a search."""
    try:
        current_url = driver.current_url
        WebDriverWait(driver, WAIT_TIME).until(
            EC.url_changes(current_url)
        )
        print(f"   [OK] URL changed to: {driver.current_url}")
        return True
    except TimeoutException:
        try:
            WebDriverWait(driver, WAIT_TIME).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "div.live-tenders-block"))
            )
            print("   [OK] Results loaded on same page.")
            return True
        except TimeoutException:
            try:
                no_results = driver.find_element(By.XPATH, "//*[contains(text(), 'No results') or contains(text(), 'no tender') or contains(text(), 'not found')]")
                print(f"   [INFO] No results found.")
                return False
            except NoSuchElementException:
                print(f"   [WARN] Could not determine if results loaded. Continuing...")
                return True

def get_search_elements():
    """Finds the search input and button elements with proper waiting."""
    try:
        search_input = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.ID, "headersearch"))
        )
        search_button = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "input.submit[value='Search']"))
        )
        return search_input, search_button
    except Exception as e:
        print(f"   [ERROR] Error finding search elements: {e}")
        return None, None

def clear_and_search(keyword):
    """Clears the input and performs a search for the given keyword."""
    try:
        # Navigate to home first
        driver.get(BASE_URL)
        time.sleep(2)
        
        search_input, search_button = get_search_elements()
        if not search_input or not search_button:
            return False
        
        # Clear using multiple methods
        driver.execute_script("arguments[0].value = '';", search_input)
        time.sleep(0.3)
        
        search_input.click()
        time.sleep(0.3)
        
        search_input.send_keys(Keys.CONTROL + "a")
        search_input.send_keys(Keys.DELETE)
        time.sleep(0.3)
        
        search_input.send_keys(keyword)
        print(f"   [OK] Entered keyword: '{keyword}'")
        
        search_button.click()
        print(f"   [OK] Search submitted.")
        return True
        
    except (StaleElementReferenceException, ElementNotInteractableException) as e:
        print(f"   [RETRY] Element issue: {e}")
        time.sleep(1)
        try:
            driver.get(BASE_URL)
            time.sleep(2)
            search_input, search_button = get_search_elements()
            if search_input and search_button:
                driver.execute_script("arguments[0].value = arguments[1];", search_input, keyword)
                time.sleep(0.5)
                search_button.click()
                print(f"   [OK] Entered keyword: '{keyword}' (recovered)")
                return True
        except:
            pass
        return False
    except Exception as e:
        print(f"   [ERROR] Error during search: {e}")
        return False

def save_to_tender18_table(tender_data_list):
    """Save scraped tenders to the tender18_tenders table."""
    saved_count = 0
    
    # Try to get Supabase client
    client = _get_client()
    
    # If no client, save to CSV as fallback
    if client is None:
        print("[WARN] No Supabase client available. Saving to CSV instead.")
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        filename = f"tender18_results_{timestamp}.csv"
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
            if not data.get('detail_url'):
                print(f"   [WARN] Skipping - no detail URL")
                continue
            
            # Check if already exists by URL
            url_hash = hashlib.md5(data['detail_url'].encode('utf-8')).hexdigest()
            
            # Check for duplicate
            try:
                check_res = client.table("tender18_tenders").select("id").eq("url_hash", url_hash).execute()
                if check_res.data and len(check_res.data) > 0:
                    print(f"   [SKIP] Duplicate: {safe_get_string(data.get('title'), 'Untitled')}")
                    continue
            except Exception as e:
                print(f"   [WARN] Duplicate check failed: {e}")
            
            # Insert into tender18_tenders table
            row = {
                "title": data.get('title'),
                "reference_number": data.get('ref_no'),
                "organization": data.get('agency'),
                "deadline": data.get('due_date'),
                "estimated_value": data.get('tender_value'),
                "location": data.get('location'),
                "source_url": data.get('detail_url'),
                "url_hash": url_hash,
                "keywords_matched": [data['keyword']] if data.get('keyword') else [],
                "scraped_at": datetime.now(timezone.utc).isoformat(),
            }
            
            try:
                res = client.table("tender18_tenders").insert(row).execute()
                if res.data and len(res.data) > 0:
                    saved_count += 1
                    print(f"   [OK] Saved: {safe_get_string(data.get('title'), 'Untitled')}")
                else:
                    print(f"   [WARN] Failed to save: {safe_get_string(data.get('title'), 'Untitled')}")
            except Exception as e:
                print(f"   [ERROR] Insert failed: {e}")
                
        except Exception as e:
            print(f"   [ERROR] Error saving tender: {e}")
    
    return saved_count

def scrape_keyword_with_pagination(keyword, max_pages=MAX_PAGES):
    """Scrape a single keyword with pagination support."""
    all_results = []
    current_page = 1
    
    print(f"\n{'='*50}")
    print(f"[SEARCH] Searching for keyword: '{keyword}'")
    print(f"{'='*50}")
    
    try:
        # Navigate to home and search
        driver.get(BASE_URL)
        time.sleep(2)
        
        search_success = clear_and_search(keyword)
        if not search_success:
            print(f"   [ERROR] Failed to perform search for '{keyword}'. Skipping...")
            return []
        
        results_loaded = wait_for_results()
        if not results_loaded:
            return []
        
        # Scrape first page
        results = scrape_current_page(keyword, current_page)
        if results:
            print(f"   [DATA] Page {current_page}: Found {len(results)} tenders")
            all_results.extend(results)
        else:
            print(f"   [WARN] No results on page {current_page}")
        
        # Scrape subsequent pages
        while current_page < max_pages:
            # Check if we're on the last page
            if is_last_page():
                print(f"   [INFO] Reached last page. Stopping pagination.")
                break
            
            # Try to go to next page
            time.sleep(1)
            if not go_to_next_page():
                print(f"   [INFO] No more pages to scrape.")
                break
            
            current_page += 1
            time.sleep(3)  # Wait for page to load
            
            # Scrape the next page
            results = scrape_current_page(keyword, current_page)
            if results:
                print(f"   [DATA] Page {current_page}: Found {len(results)} tenders")
                all_results.extend(results)
            else:
                print(f"   [WARN] No results on page {current_page}")
                # If no results on a page, stop pagination
                break
            
            # Small delay between pages
            time.sleep(1)
        
        print(f"   [SUMMARY] Total {len(all_results)} tenders found for '{keyword}' across {current_page} page(s)")
        
    except Exception as e:
        print(f"   [ERROR] Error processing keyword '{keyword}': {e}")
        import traceback
        traceback.print_exc()
    
    return all_results

# --- Main Scraping Loop ---
all_scraped_data = []

try:
    print(f"[START] Navigating to {BASE_URL}...")
    driver.get(BASE_URL)
    
    WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.ID, "headersearch"))
    )
    print("[OK] Page loaded successfully.")
    
    processed_count = 0
    total_keywords = len(KEYWORDS)
    
    for keyword in KEYWORDS:
        processed_count += 1
        print(f"\n{'='*50}")
        print(f"[PROGRESS {processed_count}/{total_keywords}] Processing keyword: '{keyword}'")
        print(f"{'='*50}")
        
        # Scrape keyword with pagination
        results = scrape_keyword_with_pagination(keyword, MAX_PAGES)
        
        if results:
            all_scraped_data.extend(results)
            print(f"   [TOTAL] Added {len(results)} tenders from '{keyword}'")
        else:
            print(f"   [WARN] No tenders found for '{keyword}'")
        
        # Delay between keywords
        if keyword != KEYWORDS[-1]:
            print(f"   [WAIT] Waiting {PAGE_LOAD_DELAY} seconds before next keyword...")
            time.sleep(PAGE_LOAD_DELAY)

except KeyboardInterrupt:
    print("\n[STOP] Scraper stopped by user")
except Exception as e:
    print(f"\n[ERROR] A critical error occurred: {e}")
    import traceback
    traceback.print_exc()

finally:
    print("\n" + "="*50)
    print("[DONE] Scraping Complete")
    print(f"[DONE] Total tenders scraped: {len(all_scraped_data)}")
    print("="*50)
    try:
        driver.quit()
    except:
        pass

# --- Save Data ---
if all_scraped_data:
    print(f"\n[DATA] Total tenders scraped: {len(all_scraped_data)}")
    
    # Remove duplicates by URL before saving
    unique_tenders = {}
    for tender in all_scraped_data:
        url = tender.get('detail_url')
        if url and url not in unique_tenders:
            unique_tenders[url] = tender
    
    unique_list = list(unique_tenders.values())
    print(f"[DATA] {len(unique_list)} unique tenders after deduplication")
    
    # Save to tender18_tenders table (or CSV as fallback)
    saved = save_to_tender18_table(unique_list)
    print(f"[OK] Saved {saved} tenders to database.")
    
    # Print sample
    print("\n[Sample of scraped data:]")
    for i, item in enumerate(unique_list[:5]):
        title = safe_get_string(item.get('title'), 'Untitled')
        ref = safe_get_string(item.get('ref_no'), 'No Ref')
        keyword = safe_get_string(item.get('keyword'), 'Unknown')
        print(f"  {i+1}. {title[:60]} - {ref} - [{keyword}]")
    
    if len(unique_list) > 5:
        print(f"  ... and {len(unique_list) - 5} more")
else:
    print("[WARN] No data was scraped.")