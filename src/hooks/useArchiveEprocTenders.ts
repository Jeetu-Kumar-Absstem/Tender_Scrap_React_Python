// src/hooks/useArchiveEprocTenders.ts
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { supabase } from '../lib/supabase'
import type { Tender, ArchivedEprocTender } from '../types/tender'

// eslint-disable-next-line @typescript-eslint/no-explicit-any
const db = supabase as any

export type { ArchivedEprocTender }

async function fetchArchiveEprocTenders(): Promise<ArchivedEprocTender[]> {
  // Trigger shift procedure to auto-move expired tenders (deadline < current_date)
  try {
    await db.rpc('shift_expired_eproc_tenders')
  } catch (err) {
    console.warn('[useArchiveEproc] RPC shift_expired_eproc_tenders error/missing:', err)
  }

  const { data, error } = await db
    .from('archieve_eproc_tenders')
    .select('*')
    .order('archived_at', { ascending: false })

  if (error) {
    console.error('[useArchiveEproc] Error fetching archieve_eproc_tenders:', error)
    return []
  }

  return (data || []) as ArchivedEprocTender[]
}

export function useArchiveEprocTenders() {
  return useQuery({
    queryKey: ['archive-eproc-tenders'],
    queryFn: fetchArchiveEprocTenders,
    staleTime: 60_000,
    gcTime: 1000 * 60 * 60 * 24,
    refetchOnMount: true,
    refetchOnWindowFocus: false,
    refetchOnReconnect: false,
  })
}

export function useArchiveEprocActions() {
  const queryClient = useQueryClient()

  const archiveAndDelete = useMutation({
    mutationFn: async ({
      tender,
      reason = 'expired',
    }: {
      tender: Tender
      reason?: 'expired' | 'manual_delete' | 'pipeline_cleanup'
    }) => {
      // 1. Check if already archived
      const { data: existing } = await db
        .from('archieve_eproc_tenders')
        .select('id')
        .eq('original_id', tender.id)
        .maybeSingle()

      if (existing) {
        if (!tender.deleted_at) {
          await db
            .from('tenders')
            .update({ deleted_at: new Date().toISOString() })
            .eq('id', tender.id)
        }
        return tender.id
      }

      // 2. Insert into archieve_eproc_tenders
      const archiveRow = {
        original_id: tender.id,
        run_id: tender.run_id,
        title: tender.title,
        reference_number: tender.reference_number,
        organization: tender.organization,
        deadline: tender.deadline,
        estimated_value: tender.estimated_value,
        location: tender.location,
        document_urls: tender.document_urls || [],
        source_site: tender.source_site,
        source_url: tender.source_url,
        url_hash: tender.url_hash,
        site_type: tender.site_type,
        keywords_matched: tender.keywords_matched || [],
        status: tender.status,
        scraped_at: tender.scraped_at,
        user_status: tender.user_status || 'active',
        archived_at: new Date().toISOString(),
        archive_reason: reason,
      }

      const { error: archiveError } = await db
        .from('archieve_eproc_tenders')
        .insert(archiveRow)

      if (archiveError) throw new Error(`Archive insert failed: ${archiveError.message}`)

      // 3. Soft delete from tenders table
      const { error: deleteError } = await db
        .from('tenders')
        .update({ deleted_at: new Date().toISOString() })
        .eq('id', tender.id)

      if (deleteError) throw new Error(`Soft delete failed: ${deleteError.message}`)

      return tender.id
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['tenders'] })
      queryClient.invalidateQueries({ queryKey: ['archive-eproc-tenders'] })
    },
  })

  return { archiveAndDelete }
}

export function useDeleteArchiveEprocTender() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async (id: string) => {
      const { error } = await db
        .from('archieve_eproc_tenders')
        .delete()
        .eq('id', id)
      if (error) throw new Error(error.message)
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['archive-eproc-tenders'] })
    },
  })
}
