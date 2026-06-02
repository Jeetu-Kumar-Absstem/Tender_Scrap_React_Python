// src/hooks/useTenderActions.ts
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { supabase } from '../lib/supabase'
import type { UserStatus } from '../types/tender'

// eslint-disable-next-line @typescript-eslint/no-explicit-any
const db = supabase as any

export function useTenderActions() {
  const qc = useQueryClient()
  const invalidate = () => {
    qc.invalidateQueries({ queryKey: ['tenders'] })
    qc.invalidateQueries({ queryKey: ['tenders', 'today'] })
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
    mutationFn: async (id: string) => {
      const { error } = await db.from('tenders')
        .delete().eq('id', id)
      if (error) throw new Error(error.message)
    },
    onSuccess: invalidate,
  })

  return { setStatus, deleteTender }
}
