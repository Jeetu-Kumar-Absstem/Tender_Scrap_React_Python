# test_eprocure.py
# Usage: python test_eprocure.py

import httpx
from bs4 import BeautifulSoup

KEYWORDS = ["psa plant", "psa", "oxygen", "nitrogen"]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-IN,en-GB;q=0.9,en;q=0.8",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
}

ENDPOINTS = [
    "https://eprocure.gov.in/eprocure/app?component=%24DirectLink&page=FrontEndLatestActiveTendersList&service=direct&session=T",
    "https://eprocure.gov.in/eprocure/app",
    "https://eprocure.gov.in/mmp/latestactivetenders",
]

def main():
    print("[->] Testing eProcure scraper")

    with httpx.Client(timeout=25, follow_redirects=True, headers=HEADERS) as client:

        # Warm up session
        try:
            r = client.get("https://eprocure.gov.in/", timeout=10)
            print("[OK] Session warmup: status " + str(r.status_code))
        except Exception as e:
            print("[!] Warmup failed: " + str(e))

        html = None
        working_url = None
        for endpoint in ENDPOINTS:
            try:
                print("[->] Trying: " + endpoint)
                resp = client.get(endpoint, headers={**HEADERS, "Referer": "https://eprocure.gov.in/"}, timeout=20)
                print("    Status: " + str(resp.status_code) + " | Size: " + str(len(resp.text)))
                if resp.status_code == 200 and len(resp.text) > 500:
                    html = resp.text
                    working_url = endpoint
                    print("[OK] Got HTML from: " + endpoint)
                    break
            except Exception as e:
                print("    Failed: " + str(e))
                continue

        if not html:
            print("[FAIL] All endpoints failed - eProcure is blocking requests")
            return

        # Save raw HTML
        with open("eprocure_raw.html", "w", encoding="utf-8") as f:
            f.write(html)
        print("[OK] Raw HTML saved to eprocure_raw.html")

        # Check keyword presence
        for kw in KEYWORDS:
            found = kw.lower() in html.lower()
            print("  Keyword '" + kw + "': " + ("FOUND" if found else "not found"))

        # Parse tables
        soup = BeautifulSoup(html, "html.parser")
        tables = soup.find_all("table")
        print("\n[i] Found " + str(len(tables)) + " tables on page")

        tender_table = None
        for i, t in enumerate(tables):
            headers = [th.get_text(strip=True) for th in t.find_all("th")]
            rows = t.find_all("tr")
            print("  Table " + str(i) + ": " + str(len(rows)) + " rows, headers: " + str(headers[:5]))
            if any("tender" in h.lower() or "title" in h.lower() for h in headers):
                tender_table = t
                print("  ^ This looks like the tender table!")

        if not tender_table and tables:
            # Pick biggest table
            tender_table = max(tables, key=lambda t: len(t.find_all("tr")))
            print("\n[i] Using largest table as fallback")

        if not tender_table:
            print("[!] No table found - check eprocure_raw.html")
            return

        rows = tender_table.find_all("tr")[1:]
        print("\n[i] Parsing " + str(len(rows)) + " rows...")
        matched = 0
        for row in rows:
            cells = [td.get_text(strip=True) for td in row.find_all("td")]
            if len(cells) < 2:
                continue
            row_text = " ".join(cells).lower()
            kw_match = [kw for kw in KEYWORDS if kw.lower() in row_text]
            if kw_match:
                matched += 1
                print("\n[MATCH] Keywords: " + str(kw_match))
                for j, cell in enumerate(cells[:6]):
                    print("  col" + str(j) + ": " + cell[:100])

        print("\n[DONE] Matched " + str(matched) + " rows with keywords out of " + str(len(rows)) + " total rows")


if __name__ == "__main__":
    main()