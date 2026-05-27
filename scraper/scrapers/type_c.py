"""
scraper/scrapers/type_c.py
──────────────────────────
Type C scraper — API / structured data sources.
Covers: GeM portal, eProcure/CPPP

These sites return structured data — no LLM needed.
Fields are mapped directly to TenderRecord schema.
"""

from __future__ import annotations
import hashlib
import structlog
import httpx
from datetime import datetime, timezone
from typing import Optional

from ..core.schema import SiteConfig, TenderRecord, TenderStatus, INCLUDE_KEYWORDS
from ..llm.extractor import BaseLLMExtractor

log = structlog.get_logger()

_HEADERS = {
    "User-Agent":      "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124.0.0.0",
    "Accept":          "application/json, text/html, */*",
    "Accept-Language": "en-IN,en;q=0.9",
}


def _make_record(
    site_config: SiteConfig,
    run_id: Optional[str],
    title: Optional[str],
    reference_number: Optional[str],
    organization: Optional[str],
    deadline: Optional[str],
    estimated_value: Optional[str],
    location: Optional[str],
    document_urls: list[str],
    source_url: str,
    keywords_matched: list[str],
) -> TenderRecord:
    url_hash = hashlib.md5(source_url.encode()).hexdigest()
    return TenderRecord(
        source_site=site_config.name,
        source_url=source_url,
        site_type=site_config.site_type.value,
        run_id=run_id,
        url_hash=url_hash,
        title=title,
        reference_number=reference_number,
        organization=organization,
        deadline=deadline,
        estimated_value=estimated_value,
        location=location,
        document_urls=document_urls,
        keywords_matched=keywords_matched,
        status=TenderStatus.PASS,
        scraped_at=datetime.now(timezone.utc).isoformat(),
    )


# ─── GeM scraper ─────────────────────────────────────────────
def _scrape_gem(
    site_config: SiteConfig,
    run_id: Optional[str],
) -> list[TenderRecord]:
    """
    GeM has a JSON search API.
    We search for each include keyword and collect results.
    """
    records: list[TenderRecord] = []
    seen_ids: set[str] = set()

    for keyword in INCLUDE_KEYWORDS[:5]:   # top 5 keywords
        url = f"https://mkp.gem.gov.in/api/v2/search?q={keyword}&page=1&limit=20"
        try:
            with httpx.Client(timeout=15, headers=_HEADERS) as client:
                resp = client.get(url)
                resp.raise_for_status()
                data = resp.json()

            items = data.get("data", data.get("results", data.get("items", [])))
            if not isinstance(items, list):
                continue

            for item in items:
                bid_id = str(item.get("bid_number") or item.get("id") or "")
                if bid_id in seen_ids:
                    continue
                seen_ids.add(bid_id)

                title    = item.get("name") or item.get("title") or item.get("bid_title")
                deadline = item.get("bid_end_date") or item.get("end_date")

                # Normalise date to YYYY-MM-DD
                if deadline and "T" in str(deadline):
                    deadline = str(deadline)[:10]

                record = _make_record(
                    site_config=site_config,
                    run_id=run_id,
                    title=title,
                    reference_number=item.get("bid_number") or bid_id,
                    organization=item.get("department") or item.get("org_name"),
                    deadline=deadline,
                    estimated_value=str(item.get("estimated_bid_value", "")) or None,
                    location=item.get("consignee_location") or item.get("city"),
                    document_urls=[item["url"]] if item.get("url") else [],
                    source_url=item.get("url") or url,
                    keywords_matched=[keyword],
                )
                records.append(record)

        except Exception as exc:
            log.warning("gem.keyword_failed", keyword=keyword, error=str(exc))

    log.info("gem.done", count=len(records))
    return records


# ─── eProcure / CPPP scraper ─────────────────────────────────
def _scrape_eprocure(
    site_config: SiteConfig,
    run_id: Optional[str],
) -> list[TenderRecord]:
    """
    eProcure returns an HTML table — parse rows directly.
    No LLM needed: column positions are fixed.
    """
    from bs4 import BeautifulSoup
    records: list[TenderRecord] = []

    url = "https://eprocure.gov.in/mmp/latestactivetenders"
    try:
        with httpx.Client(timeout=20, headers=_HEADERS, follow_redirects=True) as client:
            resp = client.get(url)
            resp.raise_for_status()

        soup = BeautifulSoup(resp.text, "lxml")
        rows = soup.select("table tr")[1:]   # skip header

        for row in rows:
            cells = [td.get_text(strip=True) for td in row.find_all("td")]
            if len(cells) < 5:
                continue

            title = cells[1] if len(cells) > 1 else None
            if not title:
                continue

            # Check if row is relevant to our keywords
            title_lower = title.lower()
            matched = [kw for kw in INCLUDE_KEYWORDS if kw.lower() in title_lower]
            if not matched:
                continue

            # Extract link
            link_tag = row.find("a", href=True)
            detail_url = (
                f"https://eprocure.gov.in{link_tag['href']}"
                if link_tag and link_tag["href"].startswith("/")
                else (link_tag["href"] if link_tag else url)
            )

            record = _make_record(
                site_config=site_config,
                run_id=run_id,
                title=title,
                reference_number=cells[0] if cells else None,
                organization=cells[2] if len(cells) > 2 else None,
                deadline=cells[4] if len(cells) > 4 else None,
                estimated_value=None,
                location=None,
                document_urls=[detail_url],
                source_url=detail_url,
                keywords_matched=matched,
            )
            records.append(record)

    except Exception as exc:
        log.error("eprocure.failed", error=str(exc))

    log.info("eprocure.done", count=len(records))
    return records


# ─── Main entry point ─────────────────────────────────────────
def scrape_type_c(
    site_config: SiteConfig,
    llm: BaseLLMExtractor,           # accepted for signature consistency, not used
    run_id: Optional[str] = None,
) -> list[TenderRecord]:
    """
    Returns list of TenderRecords (Type C can return multiple per site).
    llm param accepted for uniform pipeline signature but not called.
    """
    name = site_config.name.lower()

    if "gem" in name:
        return _scrape_gem(site_config, run_id)
    elif "eprocure" in name or "cppp" in name:
        return _scrape_eprocure(site_config, run_id)
    else:
        log.warning("type_c.unknown_site", site=site_config.name)
        return []
