// src/hooks/useTender18.ts
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { supabase } from '../lib/supabase'

export interface Tender18Tender {
  id: string
  title: string | null
  reference_number: string | null
  organization: string | null
  deadline: string | null
  estimated_value: string | null
  location: string | null
  source_url: string
  url_hash: string
  keywords_matched: string[]
  scraped_at: string
  deleted_at: string | null
  user_status: 'active' | 'starred' | 'done'
}

export function useTender18Tenders() {
  return useQuery({
    queryKey: ['tender18-tenders'],
    queryFn: async () => {
      console.log('[useTender18] Fetching from tender18_tenders...')
      
      try {
        const { data, error } = await supabase
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
    refetchInterval: 5000,
    staleTime: 0,
    refetchOnMount: true,
    refetchOnWindowFocus: true,
  })
}

export function useTender18Actions() {
  const queryClient = useQueryClient()

  const updateStatus = useMutation({
    mutationFn: async ({ id, user_status }: { id: string; user_status: 'active' | 'starred' | 'done' }) => {
      console.log('[useTender18] Updating status:', id, user_status)
      
      const { data, error } = await supabase
        .from('tender18_tenders')
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        .update({ user_status } as any)
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
      queryClient.invalidateQueries({ queryKey: ['tender18-tenders'] })
    },
    onError: (error) => {
      console.error('[useTender18] Update status error:', error)
    },
  })

  const deleteTender = useMutation({
    mutationFn: async (id: string) => {
      console.log('[useTender18] Deleting tender:', id)
      
      const { data, error } = await supabase
        .from('tender18_tenders')
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        .update({ deleted_at: new Date().toISOString() } as any)
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
      queryClient.refetchQueries({ queryKey: ['tender18-tenders'] })
    },
    onError: (error) => {
      console.error('[useTender18] Delete error:', error)
    },
  })

  return { updateStatus, deleteTender }
}