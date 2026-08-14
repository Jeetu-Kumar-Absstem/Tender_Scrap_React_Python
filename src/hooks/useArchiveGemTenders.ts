// src/hooks/useArchiveGemTenders.ts
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { supabase } from '../lib/supabase'
import type { GemTender } from '../types/gemTender'

// eslint-disable-next-line @typescript-eslint/no-explicit-any
const db = supabase as any

export interface ArchivedGemTender extends GemTender {
  original_id: string
  archived_at: string
  archive_reason: 'expired' | 'manual_delete' | 'pipeline_cleanup'
}

async function fetchArchiveGemTenders(): Promise<ArchivedGemTender[]> {
  const { data, error } = await db
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

      // 1. Check if already in archive (by original_id or reference_number)
      let isAlreadyArchived = false
      if (tender.id) {
        const { data: byId } = await db.from('archive_gem_tenders').select('id').eq('original_id', tender.id).maybeSingle()
        if (byId) isAlreadyArchived = true
      }
      if (!isAlreadyArchived && tender.reference_number) {
        const { data: byRef } = await db.from('archive_gem_tenders').select('id').eq('reference_number', tender.reference_number).maybeSingle()
        if (byRef) isAlreadyArchived = true
      }

      if (!isAlreadyArchived) {
        const archiveRow = {
          original_id: tender.id || crypto.randomUUID(),
          title: tender.title,
          reference_number: tender.reference_number,
          organization: tender.organization,
          location: tender.location,
          deadline: tender.deadline,
          estimated_value: tender.estimated_value,
          source_url: tender.source_url,
          keywords_matched: tender.keywords_matched || [],
          user_status: tender.user_status || 'active',
          scraped_at: tender.scraped_at,
          archived_at: new Date().toISOString(),
          archive_reason: reason,
        }

        const { error: archiveError } = await db
          .from('archive_gem_tenders')
          .insert(archiveRow)

        if (archiveError && !archiveError.message.includes('unique')) {
          console.error('[useArchiveGemActions] Archive insert error:', archiveError)
        }
      }

      // 2. Remove from gem_tenders table
      if (tender.id) {
        await db.from('gem_tenders').update({ deleted_at: new Date().toISOString() }).eq('id', tender.id)
        await db.from('gem_tenders').delete().eq('id', tender.id)
      }
      if (tender.reference_number) {
        await db.from('gem_tenders').update({ deleted_at: new Date().toISOString() }).eq('reference_number', tender.reference_number)
        await db.from('gem_tenders').delete().eq('reference_number', tender.reference_number)
      }

      // 3. Remove from today_gem_tenders table
      if (tender.id) {
        await db.from('today_gem_tenders').update({ deleted_at: new Date().toISOString() }).eq('id', tender.id)
        await db.from('today_gem_tenders').delete().eq('id', tender.id)
      }
      if (tender.reference_number) {
        await db.from('today_gem_tenders').update({ deleted_at: new Date().toISOString() }).eq('reference_number', tender.reference_number)
        await db.from('today_gem_tenders').delete().eq('reference_number', tender.reference_number)
      }
      if (tender.url_hash) {
        await db.from('today_gem_tenders').delete().eq('url_hash', tender.url_hash)
      }

      console.log('[useArchiveGem] Archive + delete success:', tender.id)
      return tender.id
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['gem-tenders'] })
      queryClient.invalidateQueries({ queryKey: ['gem-tenders', 'today'] })
      queryClient.invalidateQueries({ queryKey: ['archive-gem-tenders'] })
      queryClient.invalidateQueries({ queryKey: ['dashboard-stats'] })
    },
  })

  return { archiveAndDelete }
}

export function useDeleteArchiveGemTender() {
  const queryClient = useQueryClient()
  
  return useMutation({
    mutationFn: async (id: string) => {
      const { error } = await db
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