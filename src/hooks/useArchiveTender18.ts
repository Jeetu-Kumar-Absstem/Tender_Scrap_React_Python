// src/hooks/useArchiveTender18.ts
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { supabase } from '../lib/supabase'
import type { Tender18Tender } from '../types/tender18'

// eslint-disable-next-line @typescript-eslint/no-explicit-any
const db = supabase as any

export type ArchiveReason = 'expired' | 'manual_delete' | 'pipeline_cleanup'

export interface ArchivedTender extends Omit<Tender18Tender, 'deleted_at'> {
  original_id: string
  archived_at: string
  archive_reason: ArchiveReason
}

/**
 * Fetch all archived tenders for a given portal.
 * For now only 'tender18' is active.
 */
export function useArchiveTender18Tenders() {
  return useQuery({
    queryKey: ['archive-tender18-tenders'],
    queryFn: async () => {
      console.log('[useArchiveTender18] Fetching archive...')

      const { data, error } = await db
        .from('archive_tender18_tenders')
        .select('*')
        .order('archived_at', { ascending: false })

      if (error) {
        console.error('[useArchiveTender18] Supabase error:', error)
        throw new Error(`Supabase error: ${error.message}`)
      }

      console.log('[useArchiveTender18] Fetched:', data?.length ?? 0, 'archived tenders')
      return (data ?? []) as ArchivedTender[]
    },
    // Cache for 24 hours - archive only changes when tenders are archived
    staleTime: Infinity,
    gcTime: 1000 * 60 * 60 * 24,
    refetchOnMount: false,
    refetchOnWindowFocus: false,
    refetchOnReconnect: false,
  })
}

/**
 * Move a tender row into the archive table, then soft-delete it from the main table.
 * Call this instead of plain deleteTender whenever you want the record preserved.
 */
export function useArchiveTender18Actions() {
  const queryClient = useQueryClient()

  const archiveAndDelete = useMutation({
    mutationFn: async ({
      tender,
      reason,
    }: {
      tender: Tender18Tender
      reason: ArchiveReason
    }) => {
      console.log('[useArchiveTender18] Archiving tender:', tender.id, 'reason:', reason)

      // ── 1. Check if already archived ──────────────────────────────────────
      const { data: existing, error: checkError } = await db
        .from('archive_tender18_tenders')
        .select('id')
        .eq('original_id', tender.id)
        .maybeSingle()

      if (checkError) {
        console.error('[useArchiveTender18] Check error:', checkError)
        throw new Error(`Archive check failed: ${checkError.message}`)
      }

      if (existing) {
        console.log('[useArchiveTender18] Tender already archived, skipping insert:', tender.id)
        // Still soft-delete from main table if not already deleted
        if (!tender.deleted_at) {
          const { error: deleteError } = await db
            .from('tender18_tenders')
            .update({ deleted_at: new Date().toISOString() })
            .eq('id', tender.id)

          if (deleteError) {
            console.error('[useArchiveTender18] Delete error:', deleteError)
            throw new Error(`Main table delete failed: ${deleteError.message}`)
          }
        }
        return tender.id
      }

      // ── 2. Insert into archive ──────────────────────────────────────────
      const archiveRow = {
        original_id:      tender.id,
        title:            tender.title,
        reference_number: tender.reference_number,
        organization:     tender.organization,
        location:         tender.location,
        deadline:         tender.deadline,
        estimated_value:  tender.estimated_value,
        source_url:       tender.source_url,
        keywords_matched: tender.keywords_matched,
        user_status:      tender.user_status,
        scraped_at:       tender.scraped_at,
        archived_at:      new Date().toISOString(),
        archive_reason:   reason,
      }

      const { error: insertError } = await db
        .from('archive_tender18_tenders')
        .insert(archiveRow)

      if (insertError) {
        console.error('[useArchiveTender18] Insert error:', insertError)
        throw new Error(`Archive insert failed: ${insertError.message}`)
      }

      // ── 3. Soft-delete from main table ──────────────────────────────────
      const { error: deleteError } = await db
        .from('tender18_tenders')
        .update({ deleted_at: new Date().toISOString() })
        .eq('id', tender.id)

      if (deleteError) {
        console.error('[useArchiveTender18] Delete error:', deleteError)
        throw new Error(`Main table delete failed: ${deleteError.message}`)
      }

      console.log('[useArchiveTender18] Archive + delete success:', tender.id)
      return tender.id
    },
    onSuccess: () => {
      // Invalidate both main and archive caches
      queryClient.invalidateQueries({ queryKey: ['tender18-tenders'] })
      queryClient.invalidateQueries({ queryKey: ['archive-tender18-tenders'] })
    },
    onError: (error) => {
      console.error('[useArchiveTender18] archiveAndDelete error:', error)
    },
  })

  return { archiveAndDelete }
}