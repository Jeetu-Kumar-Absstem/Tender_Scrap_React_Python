// src/hooks/useTenderActions.ts
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { supabase } from '../lib/supabase'
import type { Tender, UserStatus } from '../types/tender'

// eslint-disable-next-line @typescript-eslint/no-explicit-any
const db = supabase as any

export function useTenderActions() {
  const qc = useQueryClient()
  const invalidate = () => {
    qc.invalidateQueries({ queryKey: ['tenders'] })
    qc.invalidateQueries({ queryKey: ['tenders', 'today'] })
    qc.invalidateQueries({ queryKey: ['archive-eproc-tenders'] })
    qc.invalidateQueries({ queryKey: ['dashboard-stats'] })
  }

  const setStatus = useMutation({
    mutationFn: async ({ id, user_status }: { id: string; user_status: UserStatus }) => {
      const { error } = await db.from('tenders').update({ user_status }).eq('id', id)
      if (error) throw new Error(error.message)
    },
    onSuccess: invalidate,
  })

  const deleteTender = useMutation({
    mutationFn: async (tenderOrId: string | Tender) => {
      let tenderObj: Tender | null = null
      const id: string = typeof tenderOrId === 'string' ? tenderOrId : tenderOrId.id

      if (typeof tenderOrId === 'object' && tenderOrId !== null) {
        tenderObj = tenderOrId
      } else {
        const { data } = await db.from('tenders').select('*').eq('id', id).maybeSingle()
        tenderObj = data as Tender | null
      }

      if (tenderObj) {
        // Check if already in archieve_eproc_tenders
        const { data: existing } = await db
          .from('archieve_eproc_tenders')
          .select('id')
          .eq('original_id', tenderObj.id)
          .maybeSingle()

        if (!existing) {
          const archiveRow = {
            original_id: tenderObj.id,
            run_id: tenderObj.run_id,
            title: tenderObj.title,
            reference_number: tenderObj.reference_number,
            organization: tenderObj.organization,
            deadline: tenderObj.deadline,
            estimated_value: tenderObj.estimated_value,
            location: tenderObj.location,
            document_urls: tenderObj.document_urls || [],
            source_site: tenderObj.source_site,
            source_url: tenderObj.source_url,
            url_hash: tenderObj.url_hash,
            site_type: tenderObj.site_type,
            keywords_matched: tenderObj.keywords_matched || [],
            status: tenderObj.status,
            scraped_at: tenderObj.scraped_at,
            user_status: tenderObj.user_status || 'active',
            archived_at: new Date().toISOString(),
            archive_reason: 'manual_delete',
          }
          await db.from('archieve_eproc_tenders').insert(archiveRow)
        }
      }

      // Soft delete from active tenders table
      await db.from('tenders')
        .update({ deleted_at: new Date().toISOString() })
        .eq('id', id)

      // Also hard delete from active tenders table to ensure complete removal from all active views
      await db.from('tenders')
        .delete()
        .eq('id', id)
    },
    onSuccess: invalidate,
  })

  return { setStatus, deleteTender }
}

