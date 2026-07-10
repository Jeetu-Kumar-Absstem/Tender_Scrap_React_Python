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
  'psa plant',
  'Oxygen Generation Plant',
  'oxygen plant',
  'psa oxygen generation plant',
  'pressure swing adsorption oxygen',
  'medical oxygen generation plant',
  'oxygen plant sitc',
  'on-site oxygen generation',
  'oxygen generator plant',
  'oxygen gas generator',
  'psa oxygen',
  'psa nitrogen plant',
  'psa nitrogen generator',
  'pressure swing adsorption nitrogen',
  'nitrogen generation plant',
  'nitrogen plant sitc',
  'on-site nitrogen generation',
  'nitrogen gas generator',
  'psa nitrogen',
  'amc psa oxygen plant',
  'cmc psa oxygen plant',
  'annual maintenance contract oxygen plant',
  'camc psa',
  'comprehensive maintenance contract psa',
  'preventive maintenance oxygen generator',
  'service contract psa plant',
  'breakdown maintenance oxygen plant',
  'psa plant amc',
  'psa plant cmc',
  'medical gas plant maintenance',
  'oxygen nitrogen plant service contract',
  'mgps maintenance',
  'psa plant spare parts',
  'oxygen plant repair maintenance',
  'vpsa',
  'liquid oxygen',
  'lox',
  'Oxygen concentrator',
  'o2 plant',
  'Nitrogen concentrator',
  'oxygen gas plant',
  'camc of oxygen plant',
  'camc of nitrogen plant',
  'Nitrogen gas plant',
  'gas generation',
  'comprehensive maintenance contract oxygen plant',
  'comprehensive maintenance contract psa nitrogen plant',
  'nitrogen generator'
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