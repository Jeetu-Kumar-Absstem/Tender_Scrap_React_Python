// src/hooks/useGemTenders.ts
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { supabase } from '../lib/supabase'
import type { GemTender } from '../types/gemTender'

export type { GemTender }

async function fetchGemTenders(): Promise<GemTender[]> {
  const { data, error } = await supabase
    .from('gem_tenders')
    .select('*')
    .is('deleted_at', null)
    .order('created_at', { ascending: false })

  if (error) throw new Error(error.message)
  return data || []
}

export function useGemTenders() {
  return useQuery({
    queryKey: ['gem-tenders'],
    queryFn: fetchGemTenders,
    // Cache for 24 hours - data only changes when scraper runs
    staleTime: Infinity, // Never stale on its own
    gcTime: 1000 * 60 * 60 * 24, // Keep in cache for 24 hours
    refetchOnMount: false, // Don't refetch on mount
    refetchOnWindowFocus: false, // Don't refetch on window focus
    refetchOnReconnect: false, // Don't refetch on reconnect
  })
}

export function useGemTendersActions() {
  const queryClient = useQueryClient()

  const updateStatus = useMutation({
    mutationFn: async ({ id, user_status }: { id: string; user_status: 'active' | 'done' | 'starred' }) => {
      const { error } = await supabase
        .from('gem_tenders')
        .update({ user_status })
        .eq('id', id)

      if (error) throw new Error(error.message)
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['gem-tenders'] })
    },
  })

  return { updateStatus }
}

// Archive mutation for GeM tenders
export function useArchiveGemActions() {
  const queryClient = useQueryClient()

  const archiveAndDelete = useMutation({
    mutationFn: async ({ 
      tender, 
      reason 
    }: { 
      tender: GemTender
      reason: 'expired' | 'manual_delete' | 'pipeline_cleanup'
    }) => {
      // 1. Insert into archive table
      const archiveRow = {
        original_id: tender.id,
        title: tender.title,
        reference_number: tender.reference_number,
        organization: tender.organization,
        location: tender.location,
        deadline: tender.deadline,
        estimated_value: tender.estimated_value,
        source_url: tender.source_url,
        keywords_matched: tender.keywords_matched || [],
        user_status: tender.user_status,
        scraped_at: tender.scraped_at,
        archived_at: new Date().toISOString(),
        archive_reason: reason,
      }

      const { error: archiveError } = await supabase
        .from('archive_gem_tenders')
        .insert(archiveRow)

      if (archiveError) throw new Error(`Archive insert failed: ${archiveError.message}`)

      // 2. Soft delete from main table
      const { error: deleteError } = await supabase
        .from('gem_tenders')
        .update({ deleted_at: new Date().toISOString() })
        .eq('id', tender.id)

      if (deleteError) throw new Error(`Soft delete failed: ${deleteError.message}`)
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['gem-tenders'] })
      queryClient.invalidateQueries({ queryKey: ['archive-gem-tenders'] })
    },
  })

  return { archiveAndDelete }
}