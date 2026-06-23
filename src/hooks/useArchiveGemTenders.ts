// src/hooks/useArchiveGemTenders.ts
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { supabase } from '../lib/supabase'
import type { GemTender } from '../types/gemTender'

export interface ArchivedGemTender extends GemTender {
  original_id: string
  archived_at: string
  archive_reason: 'expired' | 'manual_delete' | 'pipeline_cleanup'
}

async function fetchArchiveGemTenders(): Promise<ArchivedGemTender[]> {
  const { data, error } = await supabase
    .from('archive_gem_tenders')
    .select('*')
    .order('archived_at', { ascending: false })

  if (error) throw new Error(error.message)
  return data || []
}

export function useArchiveGemTenders() {
  return useQuery({
    queryKey: ['archive-gem-tenders'],
    queryFn: fetchArchiveGemTenders,
    staleTime: Infinity,
    gcTime: 1000 * 60 * 60 * 24,
    refetchOnMount: false,
    refetchOnWindowFocus: false,
    refetchOnReconnect: false,
  })
}

export function useArchiveGemActions() {
  const queryClient = useQueryClient()

  const archiveAndDelete = useMutation({
    mutationFn: async ({
      tender,
      reason,
    }: {
      tender: GemTender
      reason: 'expired' | 'manual_delete' | 'pipeline_cleanup'
    }) => {
      console.log('[useArchiveGem] Archiving tender:', tender.id, 'reason:', reason)

      // ── 1. Check if already archived ──────────────────────────────────────
      const { data: existing, error: checkError } = await supabase
        .from('archive_gem_tenders')
        .select('id')
        .eq('original_id', tender.id)
        .maybeSingle()

      if (checkError) {
        console.error('[useArchiveGem] Check error:', checkError)
        throw new Error(`Archive check failed: ${checkError.message}`)
      }

      if (existing) {
        console.log('[useArchiveGem] Tender already archived, skipping insert:', tender.id)
        // Still soft-delete from main table if not already deleted
        if (!tender.deleted_at) {
          const { error: deleteError } = await supabase
            .from('gem_tenders')
            .update({ deleted_at: new Date().toISOString() })
            .eq('id', tender.id)

          if (deleteError) {
            console.error('[useArchiveGem] Delete error:', deleteError)
            throw new Error(`Main table delete failed: ${deleteError.message}`)
          }
        }
        return tender.id
      }

      // ── 2. Insert into archive table ──────────────────────────────────────
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

      // ── 3. Soft delete from main table ────────────────────────────────────
      const { error: deleteError } = await supabase
        .from('gem_tenders')
        .update({ deleted_at: new Date().toISOString() })
        .eq('id', tender.id)

      if (deleteError) throw new Error(`Soft delete failed: ${deleteError.message}`)

      console.log('[useArchiveGem] Archive + delete success:', tender.id)
      return tender.id
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['gem-tenders'] })
      queryClient.invalidateQueries({ queryKey: ['archive-gem-tenders'] })
    },
  })

  return { archiveAndDelete }
}

export function useDeleteArchiveGemTender() {
  const queryClient = useQueryClient()
  
  return useMutation({
    mutationFn: async (id: string) => {
      const { error } = await supabase
        .from('archive_gem_tenders')
        .delete()
        .eq('id', id)
      if (error) throw new Error(error.message)
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['archive-gem-tenders'] })
    },
  })
}