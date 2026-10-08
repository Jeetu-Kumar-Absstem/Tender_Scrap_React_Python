import { useQuery } from '@tanstack/react-query'
import { supabase } from '../lib/supabase'
import type { GemTender } from './gemTender'
import { useArchiveGemTenders } from './useArchiveGemTenders'
import { useGemTenders } from './useGemTenders'

/**
 * Hook to fetch and combine both active and archived GeM tenders
 * for analysis purposes.
 */
export function useAllGemTenders() {
  const { data: activeTenders = [] } = useGemTenders()
  const { data: archivedTenders = [] } = useArchiveGemTenders()

  // Combine both lists into a single array
  // We use useQuery or a simple combine logic here.
  // Since the base hooks are already using useQuery,
  // we can just merge the results.

  const combined = [...activeTenders, ...archivedTenders]

  // Sort by date (most recent first) using scraped_at as priority
  const sorted = combined.sort((a, b) => {
    const dateA = new Date(a.scraped_at || a.created_at).getTime()
    const dateB = new Date(b.scraped_at || b.created_at).getTime()
    return dateB - dateA
  })

  return {
    data: sorted,
    total: sorted.length
  }
}
