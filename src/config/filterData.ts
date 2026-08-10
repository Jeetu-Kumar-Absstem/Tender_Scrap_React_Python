// src/config/filterData.ts

/**
 * Common states used across all portal filters
 * Extracted from tender location data
 */
export const COMMON_STATES: string[] = [
  'Andaman',
  'Andhra',
  'Arunachal',
  'Assam',
  'Bihar',
  'Chandigarh',
  'Chhattisgarh',
  'Dadra',
  'Daman',
  'Delhi',
  'Goa',
  'Gujarat',
  'Haryana',
  'Himachal',
  'Jammu',
  'Jharkhand',
  'Karnataka',
  'Kerala',
  'Ladakh',
  'Lakshadweep',
  'Madhya',
  'Maharashtra',
  'Manipur',
  'Meghalaya',
  'Mizoram',
  'Nagaland',
  'Odisha',
  'Puducherry',
  'Punjab',
  'Rajasthan',
  'Sikkim',
  'Tamil',
  'Telangana',
  'Tripura',
  'Uttar',
  'Uttarakhand',
  'West Bengal',
]

/**
 * Common keywords used across all portal filters
 * These should match the INCLUDE_KEYWORDS from type_d.py
 */
export const COMMON_KEYWORDS: string[] = [
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
    "on-site nitrogen generation system",
    "nitrogen generation plant",
    "oxygen generation system for hospital",
    "replacement of oxygen plant",
    "oxygen plant comprehensive maintenance",
    "nitrogen gas plant",
    "nitrogen psa plant",
    "nitrogen gas generation",
    "nitrogen gas generator",
    "psa nitrogen",
    "nitrogen generation plant",
    "On-site nitrogen generation system",
    "glass industry nitrogen plant",
    "pharma industry nitrogen plant",
    "food packaging nitrogen plant",
    "nitrogen plant annual maintenance",
    "comprehensive maintenance contract psa plant",
    "comprehensive maintenance contract oxygen plant",
    "comprehensive maintenance contract nitrogen plant",
    "annual maintenance contract psa plant",
    "annual maintenance contract oxygen plant",
    "annual maintenance contract nitrogen plant",
    "Comprehensive annual maintenance contract of psa oxygen generation plant",
    "Comprehensive annual maintenance contract psa plant",
    "Comprehensive annual maintenance contract nitrogen plant",
    "preventive maintenance oxygen generator",
    "oxygen plant repair maintenance",
    "nitrogen plant repair maintenance",
    "amc psa oxygen plant",
    "cmc psa oxygen plant",
    "amc psa nitrogen plant",
    "cmc psa nitrogen plant",
    "breakdown maintenance oxygen plant",
    "breakdown maintenance nitrogen plant",
    "breakdown maintenance psa plant",
    "amc psa plant",
    "cmc psa plant",
    "customized amc/cmc for pre-owned products - psa plant",
    "customized amc/cmc for pre-owned products - oxygen psa plant",
    "customized amc/cmc for pre-owned products - nitrogen psa plant",
    "customized amc/cmc for pre-owned products - nitrogen gas plant",
    "customized amc/cmc for pre-owned products - psa oxygen generation plant",
    "customized amc/cmc for pre-owned products - comprehensive annual maintenance contract of psa oxygen generation plant",
    "amc tender",
    "preventive maintenance contract",
    "comprehensive amc oxygen plant",
    "non-comprehensive amc",
    "rate contract amc psa",
    "annual rate contract",
    "spare parts supply amc",
    "warranty and post-warranty maintenance",
    "repair and maintenance of plant",
    "facility management services oxygen",
    "medical oxygen operation and maintenance tender",
    "psa oxygen plant amc tender",
    "psa nitrogen plant amc tender",
    "o&m psa plant",
    "Pressure Swing Adsorption plant",
    "Pressure Swing Adsorption oxygen generator",
    "Pressure Swing Adsorption nitrogen generator",
    "zeolite molecular sieve",
    "medical oxygen plant",
    "medical oxygen generator",
    "medical oxygen generation plant",
    "medical oxygen generation system",
    "medical gas pipeline system",
    "oxygen generation system for hospital",
    "liquid medical oxygen",
    "industrial oxygen generator",
    "industrial nitrogen generator",
    "psu industrial oxygen plant",
    "steel plant oxygen plant",
    "industrial oxygen plant",
    "industrial nitrogen plant",
    "Molecular sieve oxygen plant",
    "Molecular sieve refilling",
    "zeolite molecular sieve plant",
    "zeolite sieve replacement",
    "air dryer maintenance",
    "Zeolite molecular sieve plant",
    "Zeolite/sieve replacement",
    "Carbon molecular sieve nitrogen plant",
    "camc oxygen plant",
    "camc nitrogen plant",
    "Comprehensive Annual Maintenance Contract psa plant",
    "government hospital psa plant",
    "health department oxygen tender",
    "national health mission oxygen plant",
    "state medical services corporation",
    "cghs oxygen plant",
    "esic hospital oxygen plant",
    "railway hospital oxygen plant",
    "defence hospital oxygen plant",
    "pm cares oxygen plant",
    "turnkey supply installation testing commissioning",
    "sitc of psa oxygen plant",
    "sitc oxygen generation plant",
    "design supply installation testing commissioning psa",
    "erection and commissioning psa",
    "supply installation commissioning psa"
]

/**
 * Helper function to extract state from location string
 */
export function extractState(location: string | null): string {
  if (!location) return 'Unknown'

  const normalizedLocation = location.toLowerCase()

  for (const state of COMMON_STATES) {
    if (normalizedLocation.includes(state.toLowerCase())) {
      return state
    }
  }

  return 'Other'
}

/**
 * Get unique states from a list of tenders
 */
export function getUniqueStates<T extends { location: string | null }>(
  tenders: T[]
): string[] {
  const stateSet = new Set<string>()
  tenders.forEach((t) => {
    const state = extractState(t.location)
    stateSet.add(state)
  })
  return Array.from(stateSet).sort()
}

/**
 * Get unique keywords from a list of tenders
 */
export function getUniqueKeywords<T extends { keywords_matched?: string[] }>(
  tenders: T[]
): string[] {
  const keywordSet = new Set<string>()
  tenders.forEach((t) => {
    (t.keywords_matched || []).forEach((kw) => keywordSet.add(kw))
  })
  return Array.from(keywordSet).sort()
}

/**
 * Get all common keywords (for fallback use)
 */
export function getAllKeywords(): string[] {
  return COMMON_KEYWORDS
}