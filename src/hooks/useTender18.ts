// src/hooks/useTender18.ts
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { supabase } from '../lib/supabase'
import type { Tender18Tender } from '../types/tender18'

// Re-export so existing imports from this hook file keep working
export type { Tender18Tender } from '../types/tender18'

// tender18_tenders is not in Supabase generated types, so we escape here once
// eslint-disable-next-line @typescript-eslint/no-explicit-any
const db = supabase as any

export function useTender18Tenders() {
  return useQuery({
    queryKey: ['tender18-tenders'],
    queryFn: async () => {
      console.log('[useTender18] Fetching from tender18_tenders...')
      
      try {
        const { data, error } = await db
          .from('tender18_tenders')
          .select('*')
          .is('deleted_at', null)
          .order('scraped_at', { ascending: false })
        
        if (error) {
          console.error('[useTender18] Supabase error:', error)
          throw new Error(`Supabase error: ${error.message}`)
        }
        
        console.log('[useTender18] Fetched:', data?.length || 0, 'tenders')
        return (data ?? []) as Tender18Tender[]
      } catch (err) {
        console.error('[useTender18] Fetch error:', err)
        throw err
      }
    },
    // Cache for 24 hours - data only changes when scraper runs
    staleTime: Infinity, // Never stale on its own
    gcTime: 1000 * 60 * 60 * 24, // Keep in cache for 24 hours
    refetchOnMount: false, // Don't refetch on mount
    refetchOnWindowFocus: false, // Don't refetch on window focus
    refetchOnReconnect: false, // Don't refetch on reconnect
  })
}

export function useTender18Actions() {
  const queryClient = useQueryClient()

  const updateStatus = useMutation({
    mutationFn: async ({ id, user_status }: { id: string; user_status: Tender18Tender['user_status'] }) => {
      console.log('[useTender18] Updating status:', id, user_status)
      
      const { data, error } = await db
        .from('tender18_tenders')
        .update({ user_status })
        .eq('id', id)
        .select()
      
      if (error) {
        console.error('[useTender18] Update status error:', error)
        throw error
      }
      
      console.log('[useTender18] Update status success:', data)
      return data
    },
    onSuccess: () => {
      // Invalidate cache so data refreshes with new status
      queryClient.invalidateQueries({ queryKey: ['tender18-tenders'] })
    },
    onError: (error) => {
      console.error('[useTender18] Update status error:', error)
    },
  })

  const deleteTender = useMutation({
    mutationFn: async (id: string) => {
      console.log('[useTender18] Deleting tender:', id)
      
      const { data, error } = await db
        .from('tender18_tenders')
        .update({ deleted_at: new Date().toISOString() })
        .eq('id', id)
        .select()
      
      if (error) {
        console.error('[useTender18] Delete error:', error)
        throw error
      }
      
      console.log('[useTender18] Delete success:', data)
      return data
    },
    onSuccess: () => {
      console.log('[useTender18] Invalidating queries after delete...')
      queryClient.invalidateQueries({ queryKey: ['tender18-tenders'] })
    },
    onError: (error) => {
      console.error('[useTender18] Delete error:', error)
    },
  })

  return { updateStatus, deleteTender }
}