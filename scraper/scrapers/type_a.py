"""
scraper/scrapers/type_a.py
HLL Lifecare scraper for the public tender listing.

This module keeps the original helper structure from the standalone script,
but returns TenderRecord objects compatible with the existing pipeline and DB
shape.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Optional
from urllib.parse import urljoin

import pdfplumber
import requests
import structlog
from bs4 import BeautifulSoup

from ..core.schema import INCLUDE_KEYWORDS, SiteConfig, TenderRecord, TenderStatus

log = structlog.get_logger()

BASE_URL = "https://www.lifecarehll.com"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 Chrome/137.0 Safari/537.36"
    )
}

DOWNLOAD_DIR = Path(__file__).resolve().parent.parent / "downloads" / "hll"
DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)


def normalize(text: str) -> str:
    text = text.lower()
    text = re.sub(r"\s+", " ", text)
    return text


def find_matching_keywords(text: str) -> list[str]:
    text = normalize(text)
    matches: list[str] = []
    for keyword in INCLUDE_KEYWORDS:
        if keyword.lower() in text:
            matches.append(keyword)
    return matches


def get_total_pages(session: requests.Session) -> int:
    html = session.get(f"{BASE_URL}/tender", headers=HEADERS, timeout=30).text
    soup = BeautifulSoup(html, "html.parser")

    pages: list[int] = []
    for a in soup.select("#filter_pagination a"):
        href = a.get("href", "")
        match = re.search(r"/p/(\d+)", href)
        if match:
            pages.append(int(match.group(1)))

    return max(pages) if pages else 1


def scrape_tender_page(page_no: int, session: requests.Session) -> list[dict]:
    if page_no == 1:
        url = f"{BASE_URL}/tender"
    else:
        url = f"{BASE_URL}/tender/index/p/{page_no}"

    html = session.get(url, headers=HEADERS, timeout=30).text
    soup = BeautifulSoup(html, "html.parser")

    table = soup.find("table", class_="table_general")
    if not table:
        return []

    tenders: list[dict] = []
    rows = table.find_all("tr")[1:]

    for row in rows:
        cols = row.find_all("td")
        if len(cols) < 4:
            continue

        link = cols[1].find("a")
        if not link:
            continue

        tenders.append(
            {
                "title": link.get_text(strip=True),
                "url": urljoin(BASE_URL, link.get("href", "")),
                "ref_no": cols[2].get_text(strip=True),
                "category": cols[3].get_text(strip=True),
            }
        )

    return tenders


def get_detail_page_text_and_pdfs(detail_url: str, session: requests.Session) -> tuple[str, list[str]]:
    try:
        html = session.get(detail_url, headers=HEADERS, timeout=30).text
        soup = BeautifulSoup(html, "html.parser")

        page_text = soup.get_text(" ", strip=True)
        pdf_links: list[str] = []

        for a in soup.find_all("a", href=True):
            href = a["href"]
            if ".pdf" in href.lower():
                pdf_links.append(urljoin(BASE_URL, href))

        return page_text, list(set(pdf_links))
    except Exception as exc:
        log.warning("type_a.detail_page_failed", url=detail_url, error=str(exc))
        return "", []


def download_pdf(pdf_url: str, session: requests.Session) -> Optional[str]:
    try:
        filename = pdf_url.split("/")[-1]
        filename = re.sub(r"[^a-zA-Z0-9._-]", "_", filename)

        filepath = DOWNLOAD_DIR / filename

        if not filepath.exists():
            response = session.get(pdf_url, headers=HEADERS, timeout=60)
            response.raise_for_status()
            filepath.write_bytes(response.content)

        return str(filepath)
    except Exception as exc:
        log.warning("type_a.pdf_download_failed", url=pdf_url, error=str(exc))
        return None


def extract_pdf_text(pdf_file: str) -> str:
    try:
        text = ""
        with pdfplumber.open(pdf_file) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
        return text
    except Exception as exc:
        log.warning("type_a.pdf_read_failed", file=pdf_file, error=str(exc))
        return ""


def _build_record(
    site_config: SiteConfig,
    tender: dict,
    matches: list[str],
    pdf_links: list[str],
    run_id: Optional[str],
) -> TenderRecord:
    return TenderRecord(
        source_site=site_config.name,
        source_url=tender["url"],
        site_type=site_config.site_type.value,
        run_id=run_id,
        title=tender.get("title"),
        reference_number=tender.get("ref_no"),
        organization=tender.get("category"),
        deadline=None,
        estimated_value=None,
        location=None,
        document_urls=pdf_links,
        keywords_matched=matches,
        status=TenderStatus.PASS.value,
    )


def process_tender(
    tender: dict,
    site_config: SiteConfig,
    run_id: Optional[str],
    session: requests.Session,
) -> Optional[TenderRecord]:
    detail_text, pdf_links = get_detail_page_text_and_pdfs(tender["url"], session)

    combined_text = f'{tender["title"]}\n{tender.get("ref_no", "")}\n{detail_text}'

    for pdf_url in pdf_links:
        pdf_file = download_pdf(pdf_url, session)
        if not pdf_file:
            continue
        combined_text += "\n" + extract_pdf_text(pdf_file)

    matches = find_matching_keywords(combined_text)
    if not matches:
        return None

    log.info(
        "type_a.match_found",
        site=site_config.name,
        title=tender.get("title"),
        ref_no=tender.get("ref_no"),
        keywords=matches,
    )
    return _build_record(site_config, tender, matches, pdf_links, run_id)


def scrape_type_a(
    site_config: SiteConfig,
    run_id: Optional[str] = None,
) -> list[TenderRecord]:
    """
    Scrape HLL Lifecare tender listings and return matching TenderRecord rows.
    """
    if site_config.name != "HLL Lifecare":
        log.info("type_a.unsupported_site", site=site_config.name, url=site_config.url)
        return []

    session = requests.Session()
    session.headers.update(HEADERS)

    try:
        total_pages = get_total_pages(session)
        log.info("type_a.pages_found", site=site_config.name, pages=total_pages)

        all_records: list[TenderRecord] = []
        seen_keys: set[str] = set()

        for page_no in range(1, total_pages + 1):
            try:
                tenders = scrape_tender_page(page_no, session)
            except Exception as exc:
                log.warning("type_a.page_failed", site=site_config.name, page=page_no, error=str(exc))
                continue

            for tender in tenders:
                try:
                    key = tender.get("ref_no") or tender.get("url")
                    if key in seen_keys:
                        continue
                    seen_keys.add(key)

                    record = process_tender(tender, site_config, run_id, session)
                    if record:
                        all_records.append(record)
                except Exception as exc:
                    log.warning(
                        "type_a.tender_failed",
                        site=site_config.name,
                        title=tender.get("title"),
                        error=str(exc),
                    )

        log.info("type_a.done", site=site_config.name, records=len(all_records))
        return all_records
    finally:
        session.close()
