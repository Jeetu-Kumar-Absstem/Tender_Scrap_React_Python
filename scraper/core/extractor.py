"""
scraper/core/extractor.py
─────────────────────────
Shared extraction pipeline — called by ALL scraper types (A/B/C/D).

Scrapers produce raw HTML/text.
This module turns raw content into a normalised TenderRecord.

Steps:
  1. clean_html()              — strip noise tags → plain text
  2. check_reject_keywords()   — free string search, bail early
  3. extract_keyword_windows() — find keyword context, trim to budget
  4. llm.extract()             — structured JSON from context
  5. build TenderRecord        — merge metadata + LLM output
"""

from __future__ import annotations
import re
import structlog
from bs4 import BeautifulSoup
from typing import Optional

from .schema import (
    TenderRecord, TenderStatus, SiteConfig,
    INCLUDE_KEYWORDS, REJECT_KEYWORDS,
)
from ..llm.extractor import BaseLLMExtractor

log = structlog.get_logger()

# Tags that are pure noise — remove before any processing
_NOISE_TAGS = [
    "script", "style", "noscript", "nav", "footer", "header",
    "aside", "iframe", "svg", "img", "form", "button",
    "meta", "link", "head", "figure", "picture",
]

# Max chars sent to LLM — keeps token cost low
_MAX_CONTEXT_CHARS = 3_000
_WINDOW_CHARS      = 400   # context radius around each keyword hit


# ─── 1. HTML cleaning ────────────────────────────────────────
def clean_html(raw_html: str) -> str:
    """
    Strips noise tags, returns visible plain text.
    Typical: 200KB HTML → 10–20KB text.
    """
    soup = BeautifulSoup(raw_html, "lxml")
    for tag in soup(_NOISE_TAGS):
        tag.decompose()

    text = soup.get_text(separator="\n")
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    return "\n".join(lines)


# ─── 2. Reject keyword check (free — no LLM) ────────────────
def check_reject_keywords(
    text: str,
    reject_keywords: list[str] = REJECT_KEYWORDS,
) -> list[str]:
    text_lower = text.lower()
    return [kw for kw in reject_keywords if kw.lower() in text_lower]


# ─── 3. Keyword window extraction ────────────────────────────
def extract_keyword_windows(
    text: str,
    keywords: list[str] = INCLUDE_KEYWORDS,
    window_chars: int = _WINDOW_CHARS,
    max_total_chars: int = _MAX_CONTEXT_CHARS,
) -> tuple[str, list[str]]:
    """
    Returns (context_text, matched_keywords).
    context_text: merged deduped windows around every keyword hit.
    Reduces 15KB clean text → ~0.5–2KB for LLM. 90%+ token saving.
    """
    text_lower  = text.lower()
    matched_kws: list[str] = []
    intervals:   list[tuple[int, int]] = []

    for kw in keywords:
        kw_lower = kw.lower()
        pos = 0
        while True:
            idx = text_lower.find(kw_lower, pos)
            if idx == -1:
                break
            if kw not in matched_kws:
                matched_kws.append(kw)
            start = max(0, idx - window_chars)
            end   = min(len(text), idx + len(kw) + window_chars)
            intervals.append((start, end))
            pos = idx + 1

    if not intervals:
        return "", []

    # Merge overlapping / adjacent intervals
    intervals.sort()
    merged = [list(intervals[0])]
    for start, end in intervals[1:]:
        if start <= merged[-1][1] + 50:
            merged[-1][1] = max(merged[-1][1], end)
        else:
            merged.append([start, end])

    # Build context string, capped at max_total_chars
    chunks: list[str] = []
    total = 0
    for start, end in merged:
        chunk = text[start:end].strip()
        if total + len(chunk) > max_total_chars:
            remaining = max_total_chars - total
            if remaining > 100:
                chunks.append(chunk[:remaining] + "…")
            break
        chunks.append(chunk)
        total += len(chunk)

    return "\n\n---\n\n".join(chunks), matched_kws


# ─── 4 & 5. Full pipeline ────────────────────────────────────
def process_page(
    raw_html: str,
    site_config: SiteConfig,
    llm: BaseLLMExtractor,
    run_id: Optional[str] = None,
) -> Optional[TenderRecord]:
    """
    Master pipeline function.
    Called identically by Type A, B, C, D scrapers.

    Returns:
      None             — no include keywords found (irrelevant page)
      TenderRecord with status=REJECT — reject keyword hit
      TenderRecord with status=PASS   — new tender ready for DB
      TenderRecord with status=ERROR  — LLM or parse failure
    """
    record = TenderRecord(
        source_site=site_config.name,
        source_url=site_config.url,
        site_type=site_config.site_type.value,
        run_id=run_id,
    )

    # Step 1: clean
    clean_text = clean_html(raw_html)
    log.debug("extractor.clean", site=site_config.name, chars=len(clean_text))

    # Step 2: reject check (zero cost)
    reject_hits = check_reject_keywords(clean_text)
    if reject_hits:
        log.info("extractor.rejected", site=site_config.name, hits=reject_hits)
        record.status = TenderStatus.REJECT
        return record

    # Step 3: keyword windows
    context_text, matched_kws = extract_keyword_windows(clean_text)
    if not matched_kws:
        log.info("extractor.no_keywords", site=site_config.name)
        return None   # page has nothing relevant — don't store

    record.keywords_matched = matched_kws
    log.info(
        "extractor.keywords_found",
        site=site_config.name,
        keywords=matched_kws,
        context_chars=len(context_text),
    )

    # Step 4: LLM extraction
    try:
        extracted = llm.extract(context_text)
    except Exception as exc:
        log.error("extractor.llm_failed", site=site_config.name, error=str(exc))
        record.status = TenderStatus.ERROR
        return record

    # Step 5: merge
    record.title            = extracted.get("title")
    record.reference_number = extracted.get("reference_number")
    record.organization     = extracted.get("organization")
    record.deadline         = extracted.get("deadline")
    record.estimated_value  = extracted.get("estimated_value")
    record.location         = extracted.get("location")
    record.document_urls    = extracted.get("document_urls") or []
    record.status           = TenderStatus.PASS

    return record
