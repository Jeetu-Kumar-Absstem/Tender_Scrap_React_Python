// src/hooks/useGemTenders.ts
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { supabase } from '../lib/supabase'
import type { GemTender } from '../types/gemTender'

export type { GemTender }

// eslint-disable-next-line @typescript-eslint/no-explicit-any
const db = supabase as any

async function fetchGemTenders(): Promise<GemTender[]> {
  const { data, error } = await db
    .from('gem_tenders')
    .select('*')
    .is('deleted_at', null)
    .order('created_at', { ascending: false })

  if (error) throw new Error(error.message)
  return data || []
}

async function fetchGemTodayTenders(): Promise<GemTender[]> {
  const { data, error } = await db
    .from('today_gem_tenders')
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
    staleTime: Infinity,
    gcTime: 1000 * 60 * 60 * 24,
    refetchOnMount: false,
    refetchOnWindowFocus: false,
    refetchOnReconnect: false,
  })
}

export function useGemTodayTenders() {
  return useQuery({
    queryKey: ['gem-tenders', 'today'],
    queryFn: fetchGemTodayTenders,
    staleTime: Infinity,
    gcTime: 1000 * 60 * 60 * 24,
    refetchOnMount: false,
    refetchOnWindowFocus: false,
    refetchOnReconnect: false,
  })
}

export function useGemTendersActions() {
  const queryClient = useQueryClient()

  const updateStatus = useMutation({
    mutationFn: async ({ id, user_status }: { id: string; user_status: 'active' | 'done' | 'starred' }) => {
      const { error } = await db
        .from('gem_tenders')
        .update({ user_status })
        .eq('id', id)

      if (error) throw new Error(error.message)
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['gem-tenders'] })
      queryClient.invalidateQueries({ queryKey: ['gem-tenders', 'today'] })
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