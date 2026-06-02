"""
scraper/core/schema.py
─────────────────────
Single source of truth for:
  - TenderRecord dataclass (mirrors Supabase tenders table exactly)
  - SiteConfig dataclass (one entry per website)
  - All 40 site configurations
  - Keyword lists
"""

from __future__ import annotations
import hashlib
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional, Literal
from enum import Enum


# ─── Enums ──────────────────────────────────────────────────
class SiteType(str, Enum):
    A = "A"   # Static HTML
    B = "B"   # JS rendered (Playwright)
    C = "C"   # API / structured/ playwright/selenium optional
    D = "D"   # Login / subscription wall


class TenderStatus(str, Enum):
    PASS   = "PASS"
    REJECT = "REJECT"
    ERROR  = "ERROR"


# ─── Keyword lists ───────────────────────────────────────────
INCLUDE_KEYWORDS: list[str] =[
    # From PSA Oxygen Plant
    "oxygen plant", "psa oxygen generation plant", "pressure swing adsorption oxygen",
    "medical oxygen generation plant", "oxygen plant sitc", "on-site oxygen generation",
    "oxygen generator plant", "oxygen gas generator", "psa oxygen",

    # PSA Nitrogen Plant
    "psa nitrogen plant", "psa nitrogen generator", "pressure swing adsorption nitrogen",
    "nitrogen generation plant", "nitrogen plant sitc", "on-site nitrogen generation",
    "nitrogen gas generator", "psa nitrogen",
    
    # From AMC / CMC - PSA
    "amc psa oxygen plant", "cmc psa oxygen plant", "annual maintenance contract oxygen plant",
    "camc psa", "comprehensive maintenance contract", "preventive maintenance oxygen generator",
    "service contract psa plant", "breakdown maintenance oxygen plant",
    
    # From Other
    "psa plant amc", "psa plant cmc", "medical gas plant maintenance",
    "oxygen nitrogen plant service contract", "mgps maintenance",
    "psa plant spare parts", "oxygen plant repair maintenance",
    
    # Additional from your INCLUDE_KEYWORDS (merged where applicable)
    "vpsa", "liquid oxygen", "lox", "concentrator", "o2 plant", "gas plant", "gas generation"
]

REJECT_KEYWORDS: list[str] = [
    # Add keywords that disqualify a tender
    # e.g. "consultancy", "printing", "civil work"
]


# ─── TenderRecord ────────────────────────────────────────────
@dataclass
class TenderRecord:
    """
    Mirrors the Supabase `tenders` table row exactly.
    Every scraper type (A/B/C/D) must produce this shape.
    """
    # Scraper fills these
    source_site:   str = ""
    source_url:    str = ""
    site_type:     str = ""
    scraped_at:    str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    run_id:        Optional[str] = None

    # Dedup keys
    url_hash:      str = ""       # md5(source_url) — set automatically

    # LLM fills these (None = not found on page)
    title:             Optional[str] = None
    reference_number:  Optional[str] = None
    organization:      Optional[str] = None
    deadline:          Optional[str] = None    # YYYY-MM-DD
    estimated_value:   Optional[str] = None
    location:          Optional[str] = None
    document_urls:     list[str] = field(default_factory=list)

    # Pipeline metadata
    keywords_matched:  list[str] = field(default_factory=list)
    status:            str = TenderStatus.PASS

    def __post_init__(self):
        if self.source_url and not self.url_hash:
            self.url_hash = hashlib.md5(
                self.source_url.encode("utf-8")
            ).hexdigest()

    def to_supabase_row(self) -> dict:
        """Returns dict ready for supabase.table('tenders').insert()"""
        return {
            "run_id":           self.run_id,
            "title":            self.title,
            "reference_number": self.reference_number,
            "organization":     self.organization,
            "deadline":         self.deadline,
            "estimated_value":  self.estimated_value,
            "location":         self.location,
            "document_urls":    self.document_urls,
            "source_site":      self.source_site,
            "source_url":       self.source_url,
            "url_hash":         self.url_hash,
            "site_type":        self.site_type,
            "keywords_matched": self.keywords_matched,
            "status":           self.status,
            "scraped_at":       self.scraped_at,
        }


# ─── SiteConfig ──────────────────────────────────────────────
@dataclass
class SiteConfig:
    name:      str
    url:       str
    site_type: SiteType
    notes:     str = ""
    use_scrapedo: bool = False   # route through scrape.do proxy


# ─── All 40 sites ────────────────────────────────────────────
SITES: list[SiteConfig] = [

    # ── Type C — API/structured (no LLM needed) ─────────────
    SiteConfig(
        name="GeM",
        url="https://bidplus.gem.gov.in/all-bids#",
        site_type=SiteType.C,
        notes="playwright and selenium scarper",
    ),
    SiteConfig(
        name="eProcure / CPPP",
        url="https://eprocure.gov.in/eprocure/app",
        site_type=SiteType.B,
        notes="Central NIC portal. Same Playwright scraper as state portals.",
    ),

    # ── Type B — NIC portal family (one Playwright scraper) ─
    SiteConfig(name="Andaman & Nicobar", url="https://eprocure.andamannicobar.gov.in/nicgep/app",         site_type=SiteType.B),
    SiteConfig(name="Arunachal Pradesh", url="https://arunachaltenders.gov.in/nicgep/app",         site_type=SiteType.B),
    SiteConfig(name="Assam",             url="https://assamtenders.gov.in/nicgep/app",             site_type=SiteType.B),
    SiteConfig(name="Chandigarh",        url="https://etenders.chd.nic.in/nicgep/app",             site_type=SiteType.B),
    SiteConfig(name="Dadra & NH",        url="https://dnhtenders.gov.in/nicgep/app",               site_type=SiteType.B),
    SiteConfig(name="Daman & Diu",       url="https://ddtenders.gov.in/nicgep/app",                site_type=SiteType.B),
    SiteConfig(name="Delhi",             url="https://govtprocurement.delhi.gov.in/nicgep/app",    site_type=SiteType.B),
    SiteConfig(name="Goa",               url="https://eprocure.goa.gov.in/nicgep/app",             site_type=SiteType.B),
    SiteConfig(name="Haryana",           url="https://etenders.hry.nic.in/nicgep/app",             site_type=SiteType.B),
    SiteConfig(name="Himachal Pradesh",  url="https://hptenders.gov.in/nicgep/app",                site_type=SiteType.B),
    SiteConfig(name="Jammu & Kashmir",   url="https://jktenders.gov.in/nicgep/app",                site_type=SiteType.B),
    SiteConfig(name="Jharkhand",         url="https://jharkhandtenders.gov.in/nicgep/app",         site_type=SiteType.B),
    SiteConfig(name="Karnataka",         url="https://eproc.karnataka.gov.in/nicgep/app",          site_type=SiteType.B),
    SiteConfig(name="Kerala",            url="https://etenders.kerala.gov.in/nicgep/app",          site_type=SiteType.B),
    SiteConfig(name="Ladakh",            url="https://tenders.ladakh.gov.in/nicgep/app",           site_type=SiteType.B),
    SiteConfig(name="Lakshadweep",       url="https://tendersutl.gov.in/nicgep/app",               site_type=SiteType.B),
    SiteConfig(name="Madhya Pradesh",    url="https://mptenders.gov.in/nicgep/app",                site_type=SiteType.B),
    SiteConfig(name="Maharashtra",       url="https://mahatenders.gov.in/nicgep/app",              site_type=SiteType.B),
    SiteConfig(name="Manipur",           url="https://manipurtenders.gov.in/nicgep/app",           site_type=SiteType.B),
    SiteConfig(name="Meghalaya",         url="https://meghalayatenders.gov.in/nicgep/app",         site_type=SiteType.B),
    SiteConfig(name="Mizoram",           url="https://mizoramtenders.gov.in/nicgep/app",           site_type=SiteType.B),
    SiteConfig(name="Nagaland",          url="https://nagalandtenders.gov.in/nicgep/app",          site_type=SiteType.B),
    SiteConfig(name="Odisha",            url="https://tendersodisha.gov.in/nicgep/app",            site_type=SiteType.B),
    SiteConfig(name="Puducherry",        url="https://pudutenders.gov.in/nicgep/app",              site_type=SiteType.B),
    SiteConfig(name="Punjab",            url="https://eproc.punjab.gov.in/nicgep/app",             site_type=SiteType.B),
    SiteConfig(name="Rajasthan",         url="https://eproc.rajasthan.gov.in/nicgep/app",          site_type=SiteType.B),
    SiteConfig(name="Sikkim",            url="https://sikkimtender.gov.in/nicgep/app",             site_type=SiteType.B),
    SiteConfig(name="Tamil Nadu",        url="https://tntenders.gov.in/nicgep/app",                site_type=SiteType.B),
    SiteConfig(name="Tripura",           url="https://tripuratenders.gov.in/nicgep/app",           site_type=SiteType.B),
    SiteConfig(name="Uttar Pradesh",     url="https://etender.up.nic.in/nicgep/app",               site_type=SiteType.B),
    SiteConfig(name="Uttarakhand",       url="https://uktenders.gov.in/nicgep/app",                site_type=SiteType.B),
    SiteConfig(name="West Bengal",       url="https://wbtenders.gov.in/nicgep/app",                site_type=SiteType.B),

    # ── Type B — Non-NIC JS sites ────────────────────────────
    SiteConfig(
        name="IREPS (Railways)",
        url="https://www.ireps.gov.in/ireps/tender/tender-home.xhtml",
        site_type=SiteType.B,
        notes="Public tender list. No login for listing page.",
    ),
    SiteConfig(
        name="HLL Lifecare",
        url="https://www.lifecarehll.com/tender/",
        site_type=SiteType.A,
        notes="Medical/PSA tenders. JS rendered.",
    ),

    # ── Type A — Static HTML commercial aggregators ──────────
    # SiteConfig(
    #     name="Tender Detail",
    #     url="https://www.tenderdetail.com/tenders/search?kwd=psa+oxygen",
    #     site_type=SiteType.A,
    #     use_scrapedo=True,    # may block bots — route via scrape.do
    #     notes="Commercial aggregator. May rate-limit.",
    # ),
    # SiteConfig(
    #     name="Tenders on Time",
    #     url="https://www.tendersontime.com/tenders/oxygen-psa-tender/",
    #     site_type=SiteType.A,
    #     use_scrapedo=True,
    # ),
    # SiteConfig(
    #     name="Tender Info",
    #     url="https://www.tenderinfo.org/search.aspx?k=psa+oxygen",
    #     site_type=SiteType.A,
    #     use_scrapedo=True,
    # ),
    # SiteConfig(
    #     name="Tender18",
    #     url="https://www.tender18.com/tenders/?q=psa+oxygen",
    #     site_type=SiteType.A,
    # ),
    # SiteConfig(
    #     name="e-Tender India",
    #     url="https://www.etender.in/search/?q=psa+oxygen",
    #     site_type=SiteType.A,
    # ),

    # ── Type D — Login/paid (skip scraping, use alert emails) ─
    # These are listed for reference only. Scraper skips them.
    SiteConfig(
        name="BidAssist",
        url="https://bidassist.com",
        site_type=SiteType.D,
        notes="Paid. Configure keyword alert in their dashboard instead.",
    ),
    SiteConfig(
        name="TenderTiger",
        url="https://www.tendertiger.com",
        site_type=SiteType.D,
        notes="Paid. Configure keyword alert in their dashboard instead.",
    ),
    SiteConfig(
        name="Telangana",
        url="https://tender.telangana.gov.in",
        site_type=SiteType.D,
        notes="Login required for listing. Needs session cookie maintenance.",
    ),
]

# Convenience filters
SITES_BY_TYPE = {
    SiteType.A: [s for s in SITES if s.site_type == SiteType.A],
    SiteType.B: [s for s in SITES if s.site_type == SiteType.B],
    SiteType.C: [s for s in SITES if s.site_type == SiteType.C],
    SiteType.D: [s for s in SITES if s.site_type == SiteType.D],
}

# Current pipeline scope: Type B only
ACTIVE_SITES = SITES_BY_TYPE[SiteType.B]
