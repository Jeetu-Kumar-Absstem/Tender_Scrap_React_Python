import sys
import sysconfig

# --- START VIP PRIORITY HACK ---
for key in list(sys.modules.keys()):
    if key == 'email' or key.startswith('email.'):
        del sys.modules[key]

stdlib_path = sysconfig.get_path('stdlib')
sys.path.insert(0, stdlib_path)
import requests
sys.path.pop(0)
# --- END VIP PRIORITY HACK ---

"""
NABH Hospital Scraper — v7 (Haryana-hardcoded, single-run, stop-safe)
======================================================================
Changes from v6:
  - HARDCODED to Haryana only — no --scrape-all, no state loop
  - Single execution: runs once and exits (safe for API calls)
  - Graceful stop: Ctrl-C / SIGTERM saves what's been scraped so far
  - DB schema change: city + state merged INTO address field
    (format: "...street..., City, State, PIN")
    UI does all city/state parsing — no separate city/state columns
  - Cities for dropdown served by /api/hospitals/cities?state=Haryana
    which proxies the NABH AJAX endpoint (see test_cities.py logic)

Usage:
  python nabh_scraper.py                          ← scrape Haryana
  python nabh_scraper.py --output fallback.csv    ← also save CSV
  python nabh_scraper.py --csv-only --output out.csv

Env vars (required for Supabase output):
  SUPABASE_URL          e.g. https://xxxx.supabase.co
  SUPABASE_SERVICE_KEY  service_role key (not anon)
"""

import argparse
import csv
import os
import re
import signal
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Optional

from bs4 import BeautifulSoup
from dotenv import load_dotenv

load_dotenv()

# ── Config ────────────────────────────────────────────────────────────────────

HARDCODED_STATE = "Haryana"       # ← only state scraped

AJAX_URL   = "https://nabh.co/wp-admin/admin-ajax.php"
HEADERS    = {
    "User-Agent":       "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer":          "https://nabh.co/find-a-healthcare-organisation/",
    "X-Requested-With": "XMLHttpRequest",
    "Content-Type":     "application/x-www-form-urlencoded; charset=UTF-8",
    "Origin":           "https://nabh.co",
}
PAGE_DELAY  = 0.4
BATCH_SIZE  = 200

# ── Stop flag (set by SIGINT / Ctrl-C) ───────────────────────────────────────

_stop_requested = False

def _handle_stop(signum, frame):
    global _stop_requested
    _stop_requested = True
    print("\n[!] Stop requested — will finish current page then save what's collected…")

signal.signal(signal.SIGINT,  _handle_stop)
signal.signal(signal.SIGTERM, _handle_stop)


# ── Data model ────────────────────────────────────────────────────────────────

@dataclass
class Hospital:
    name:             str = ""
    address:          str = ""        # full address: street, city, state, pin
    phone:            str = ""
    email:            Optional[str] = None
    website:          Optional[str] = None
    accreditation_no: str = ""        # dedup key


# ── API calls ─────────────────────────────────────────────────────────────────

def get_hospitals_page(state: str, page: int = 1) -> tuple[str, int, int]:
    r = requests.post(
        AJAX_URL,
        data={"action": "get_hospitals", "selectState": state, "page": str(page)},
        headers=HEADERS,
        timeout=25,
    )
    r.raise_for_status()
    data  = r.json()
    html  = data.get("html", "")
    pag   = data.get("pagination", {})
    if isinstance(pag, dict):
        total_pages   = int(pag.get("total_pages", 1))
        total_results = int(pag.get("total_results", 0))
    elif isinstance(pag, int):
        total_pages, total_results = pag, 0
    else:
        total_pages, total_results = 1, 0
    return html, total_pages, total_results


# ── HTML parser ───────────────────────────────────────────────────────────────

def parse_hospital_html(html: str) -> list[Hospital]:
    soup      = BeautifulSoup(html, "html.parser")
    hospitals = []
    for card in soup.select(".organisation-list"):
        h    = Hospital()
        col1 = card.select_one(".hs-col-1")
        col2 = card.select_one(".hs-col-2")
        col3 = card.select_one(".hs-col-3 .d-none.d-lg-block")
        col4 = card.select_one(".hs-col-4")

        if col1:
            a      = col1.select_one("a")
            h.name = a.get_text(strip=True) if a else col1.get_text(strip=True)

        if col2:
            # address already contains city, state, pin — store as-is
            h.address = col2.get_text(strip=True)

        if col3:
            for div in col3.find_all("div", recursive=False):
                a = div.find("a")
                if a:
                    href = a.get("href", "").strip()
                    if href.startswith("mailto:"):
                        h.email = href[7:]
                    elif href:
                        h.website = href
                else:
                    text = div.get_text(strip=True)
                    if text and text != "NA":
                        if "@" in text:
                            h.email = text
                        elif text:
                            h.phone = text

        if col4:
            a        = col4.select_one("a")
            acc_text = a.get_text(strip=True) if a else col4.get_text(strip=True)
            if acc_text and acc_text != h.name:
                h.accreditation_no = acc_text

        h.phone   = h.phone or ""
        h.email   = h.email if h.email else None
        h.website = h.website if h.website else None

        if h.name and len(h.name) > 2:
            hospitals.append(h)

    return hospitals


# ── Scrape Haryana (single run) ───────────────────────────────────────────────

def scrape_haryana() -> list[Hospital]:
    state = HARDCODED_STATE
    all_hospitals: list[Hospital] = []
    print(f"\n[*] Scraping: {state} (hardcoded)")
    try:
        html, total_pages, total_results = get_hospitals_page(state, page=1)
    except Exception as e:
        print(f"    [!] Failed to fetch page 1: {e}")
        return []

    print(f"    Total results: {total_results:,}  |  Pages: {total_pages}")
    cards = parse_hospital_html(html)
    print(f"    Page  1/{total_pages} → {len(cards)} cards")
    all_hospitals.extend(cards)

    for pg in range(2, total_pages + 1):
        if _stop_requested:
            print(f"    [!] Stopped at page {pg-1}/{total_pages}")
            break
        time.sleep(PAGE_DELAY)
        try:
            html, _, _ = get_hospitals_page(state, page=pg)
            cards      = parse_hospital_html(html)
            if pg % 10 == 0 or pg == total_pages:
                print(f"    Page {pg:>4}/{total_pages} → {len(cards)} cards  (running: {len(all_hospitals) + len(cards):,})")
            all_hospitals.extend(cards)
        except Exception as e:
            print(f"    [warn] Page {pg} failed: {e}")

    return all_hospitals


# ── Supabase upsert ───────────────────────────────────────────────────────────

def upsert_to_supabase(hospitals: list[Hospital]) -> None:
    url = os.environ.get("SUPABASE_URL", "").rstrip("/")
    key = os.environ.get("SUPABASE_SERVICE_KEY", "")
    if not url or not key:
        raise RuntimeError(
            "Set SUPABASE_URL and SUPABASE_SERVICE_KEY env vars before running."
        )

    endpoint = f"{url}/rest/v1/nabh_hospitals"
    headers  = {
        "apikey":        key,
        "Authorization": f"Bearer {key}",
        "Content-Type":  "application/json",
        "Prefer":        "resolution=merge-duplicates,return=minimal",
    }

    rows = [
        {
            "name":             h.name,
            "address":          h.address,
            "phone":            h.phone or None,
            "email":            h.email,
            "website":          h.website,
            "accreditation_no": h.accreditation_no or None,
        }
        for h in hospitals
    ]

    total    = len(rows)
    inserted = 0
    for i in range(0, total, BATCH_SIZE):
        batch = rows[i : i + BATCH_SIZE]
        r     = requests.post(endpoint, headers=headers, json=batch, timeout=30)
        if r.status_code not in (200, 201):
            print(f"    [!] Supabase error {r.status_code}: {r.text[:200]}")
        else:
            inserted += len(batch)
            print(f"    Supabase upsert: {inserted}/{total} ({100*inserted//total}%)", end="\r")
    print(f"\n    [✓] Upserted {inserted:,} rows to nabh_hospitals")


# ── CSV fallback ──────────────────────────────────────────────────────────────

def save_csv(hospitals: list[Hospital], path: str) -> None:
    if not hospitals:
        print("[warn] No data to save.")
        return
    p      = Path(path)
    fields = ["name", "address", "phone", "email", "website", "accreditation_no"]
    with p.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows([asdict(h) for h in hospitals])
    print(f"\n[✓] {len(hospitals):,} rows saved → {p.resolve()}")


# ── CLI ───────────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser(
        description=f"NABH scraper (hardcoded: {HARDCODED_STATE}) → Supabase",
        epilog="""
Examples:
  python nabh_scraper.py
  python nabh_scraper.py --output haryana.csv
  python nabh_scraper.py --csv-only --output haryana.csv

Press Ctrl-C at any time to stop gracefully and save collected data.
        """
    )
    ap.add_argument("--output",   help="Also save results to CSV at this path")
    ap.add_argument("--csv-only", action="store_true", help="Skip Supabase, only save CSV (requires --output)")
    args = ap.parse_args()

    if args.csv_only and not args.output:
        ap.error("--csv-only requires --output <path>")

    hospitals = scrape_haryana()

    print(f"\n[*] Total hospitals collected: {len(hospitals):,}")

    if args.output:
        save_csv(hospitals, args.output)

    if not args.csv_only:
        upsert_to_supabase(hospitals)

    print(f"\n[done]")


if __name__ == "__main__":
    main()