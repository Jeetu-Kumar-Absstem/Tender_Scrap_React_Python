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
# INCLUDE_KEYWORDS: list[str] =[
#     'psa plant',
#     'psa nitrogen plant',
#     'psa oxygen plant',
#     'psa oxygen',
#     'psa nitrogen',
#     'oxygen plant',
#     'oxygen psa plant',
#     'oxygen gas generation',
#     'oxygen gas generator',
#     'oxygen generator',
#     'nitrogen plant',
#     'nitrogen psa plant',
#     'nitrogen gas generation',
#     'nitrogen gas generator',
#     'nitrogen generator',
#     'comprehensive maintenance contract psa plant',
#     'comprehensive maintenance contract oxygen plant',
#     'comprehensive maintenance contract nitrogen plant',
#     'annual maintenance contract psa plant',
#     'annual maintenance contract oxygen plant',
#     'annual maintenance contract nitrogen plant',
#     'psa amc',
#     'psa cmc',
#     'psa plant cmc',
#     'amc psa oxygen plant',
#     'cmc psa oxygen plant',
#     'amc psa nitrogen plant',
#     'cmc psa nitrogen plant',
#     'amc psa plany',
#     'cmc psa plant',
#     'preventive maintenance oxygen generator',
#     'oxygen plant repair maintenance',
#     'nitrogen plant repair maintenance',
#     'breakdown maintenance oxygen plant',
#     'breakdown maintenance nitrogen plant',
#     'breakdown maintenance psa plant',
#     'comprehensive annual maintenance contract of psa oxygen generation plant',
#     'comprehensive annual maintenance contract psa plant',
#     'comprehensive annual maintenance contract nitrogen plant',
#     'customized amc/cmc for pre-owned products - psa plant',
#     'customized amc/cmc for pre-owned products - oxygen psa plant',
#     'customized amc/cmc for pre-owned products - nitrogen psa plant',
#     'customized amc/cmc for pre-owned products - nitrogen gas plant',
#     'customized amc/cmc for pre-owned products - psa oxygen generation plant',
#     'customized amc/cmc for pre-owned products - comprehensive annual maintenance contract of psa oxygen generation plant',
#     # NEW UNIQUE KEYWORDS ADDED BELOW
#     'pressure swing adsorption oxygen generator',
#     'pressure swing adsorption nitrogen generator',
#     'oxygen generation plant',
#     'nitrogen generation plant',
#     'medical oxygen plant',
#     'medical oxygen generator',
#     'medical oxygen generation system',
#     'industrial oxygen generator',
#     'industrial nitrogen generator',
#     'on-site oxygen generation system',
#     'on-site nitrogen generation system',
#     'oxygen concentrator plant',
#     'zeolite molecular sieve plant',
#     'molecular sieve oxygen plant',
#     'carbon molecular sieve nitrogen plant',
#     'medical gas pipeline system mgps psa',
#     'oxygen generation system for hospital',
#     'liquid medical oxygen lmo storage psa',
#     'operation and maintenance psa',
#     'operation and maintenance of psa plant',
#     'preventive maintenance contract',
#     'comprehensive amc oxygen plant',
#     'non-comprehensive amc',
#     'rate contract amc',
#     'facility management services oxygen medical equipment',
#     'repair and maintenance of plant systems equipment',
#     'turnkey supply installation testing commissioning psa',
#     'sitc of psa oxygen plant',
#     'warranty and post-warranty maintenance',
#     'spare parts supply amc',
#     'supply installation commissioning psa',
#     'design supply installation testing commissioning psa',
#     'dsitc psa',
#     'erection and commissioning psa',
#     'retrofitting upgradation of oxygen plant',
#     'replacement of oxygen plant',
#     'refurbishment of psa plant',
#     'zeolite sieve replacement',
#     'molecular sieve refilling',
#     'compressor overhaul psa plant',
#     'air dryer maintenance',
#     'annual rate contract psa',
#     'district hospital oxygen plant',
#     'medical college oxygen plant',
#     'government hospital psa plant',
#     'health department oxygen tender',
#     'national health mission oxygen plant',
#     'state medical services corporation',
#     'cgsh oxygen plant',
#     'esic hospital oxygen plant',
#     'railway hospital oxygen plant ireps',
#     'defence hospital oxygen plant military dgafms',
#     'psu industrial oxygen plant',
#     'steel plant oxygen plant',
#     'glass industry nitrogen plant',
#     'pharma industry nitrogen plant',
#     'food packaging nitrogen plant',
#     'pm cares oxygen plant legacy renewal tenders',
# ]
# REJECT_KEYWORDS: list[str] = [
#     # Add keywords that disqualify a tender
#     # e.g. "consultancy", "printing", "civil work"
# ]

INCLUDE_KEYWORDS: list[str] =[
    # From PSA Oxygen Plant
    "psa plant","Oxygen Generation Plant","oxygen plant", "psa oxygen generation plant", "pressure swing adsorption oxygen",
    "medical oxygen generation plant", "oxygen plant sitc", "on-site oxygen generation",
    "oxygen generator plant", "oxygen gas generator", "psa oxygen",

    # PSA Nitrogen Plant
    "psa nitrogen plant", "psa nitrogen generator", "pressure swing adsorption nitrogen",
    "nitrogen generation plant", "nitrogen plant sitc", "on-site nitrogen generation",
    "nitrogen gas generator", "psa nitrogen",
    
    # From AMC / CMC - PSA
    "amc psa oxygen plant", "cmc psa oxygen plant", "annual maintenance contract oxygen plant",
    "camc psa", "comprehensive maintenance contract psa", "preventive maintenance oxygen generator",
    "service contract psa plant", "breakdown maintenance oxygen plant",
    
    # From Other
    "psa plant amc", "psa plant cmc", "medical gas plant maintenance",
    "oxygen nitrogen plant service contract", "mgps maintenance",
    "psa plant spare parts", "oxygen plant repair maintenance",
    
    # Additional from your INCLUDE_KEYWORDS (merged where applicable)
    "vpsa", "oxygen concentrator", "oxygen gas plant","nitrogen gas plant", "oxygen gas generation","nitrogen gas generation"
    , "nitrogen gas plant","nitrogen concentrator","camc of nitrogen plant","camc of oxygen plant"


    #  "o2 plant","liquid oxygen"
]


def build_dedup_signature(
    reference_number: Optional[str],
    url_hash: Optional[str],
) -> tuple[Optional[str], str]:
    """Return a normalized signature for deduplicating a tender row."""
    normalized_ref = (reference_number or "").strip() or None
    normalized_hash = (url_hash or "").strip()
    return normalized_ref, normalized_hash


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
