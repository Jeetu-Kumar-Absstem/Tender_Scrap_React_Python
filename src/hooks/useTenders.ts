import { useQuery, useInfiniteQuery } from '@tanstack/react-query'
import { supabase } from '../lib/supabase'
import type { Tender, ScrapeRun, TenderFilters, DashboardStats } from '../types/tender'

const PAGE_SIZE = 25

export function useTenders(filters: TenderFilters = {}) {
  return useInfiniteQuery({
    queryKey: ['tenders', filters],
    initialPageParam: 0,
    queryFn: async ({ pageParam = 0 }) => {
      let query = supabase
        .from('tenders')
        .select('*', { count: 'exact' })
        .is('deleted_at', null)
        .eq('status', 'PASS')
        .order('scraped_at', { ascending: false })
        .range(pageParam * PAGE_SIZE, (pageParam + 1) * PAGE_SIZE - 1)

      if (filters.source_site) query = query.eq('source_site', filters.source_site)
      if (filters.site_type)   query = query.eq('site_type', filters.site_type)
      if (filters.deadline_after)  query = query.gte('deadline', filters.deadline_after)
      if (filters.deadline_before) query = query.lte('deadline', filters.deadline_before)
      if (filters.date_from) query = query.gte('scraped_at', filters.date_from)
      if (filters.date_to)   query = query.lte('scraped_at', filters.date_to)
      if (filters.keyword) query = query.contains('keywords_matched', [filters.keyword])

      // user_status filter
      if (filters.user_status && filters.user_status !== 'all') {
        if (filters.user_status === 'active') {
          query = query.in('user_status', ['active', 'starred'])
        } else {
          query = query.eq('user_status', filters.user_status)
        }
      }

      if (filters.search) {
        query = query.or(
          `title.ilike.%${filters.search}%,organization.ilike.%${filters.search}%,reference_number.ilike.%${filters.search}%`
        )
      }

      const { data, error, count } = await query
      if (error) throw new Error(error.message)
      return {
        tenders: (data ?? []) as Tender[],
        total: count ?? 0,
        page: pageParam,
        hasMore: (pageParam + 1) * PAGE_SIZE < (count ?? 0),
      }
    },
    getNextPageParam: (last) => last.hasMore ? last.page + 1 : undefined,
  })
}

export function useTodaysTenders() {
  return useQuery({
    queryKey: ['tenders', 'today'],
    queryFn: async () => {
      const today = new Date().toISOString().split('T')[0]
      const { data, error } = await supabase
        .from('tenders')
        .select('*')
        .is('deleted_at', null)
        .eq('status', 'PASS')
        .gte('scraped_at', today)
        .order('scraped_at', { ascending: false })
      if (error) throw new Error(error.message)
      return (data ?? []) as Tender[]
    },
    refetchInterval: 5 * 60 * 1000,
  })
}

export function useDashboardStats() {
  return useQuery({
    queryKey: ['dashboard-stats'],
    queryFn: async (): Promise<DashboardStats> => {
      const today = new Date().toISOString().split('T')[0]

      const [totalRes, todayRes, runsRes, siteRes, kwRes] = await Promise.all([
        supabase.from('tenders').select('*', { count: 'exact', head: true }).is('deleted_at', null).eq('status', 'PASS'),
        supabase.from('tenders').select('*', { count: 'exact', head: true }).is('deleted_at', null).eq('status', 'PASS').gte('scraped_at', today),
        supabase.from('scrape_runs').select('started_at,status,completed_at,new_count,sites_ok,sites_total,email_sent,id').is('deleted_at', null).order('started_at', { ascending: false }).limit(1),
        supabase.from('tenders').select('source_site').is('deleted_at', null).eq('status', 'PASS'),
        supabase.from('tenders').select('keywords_matched').is('deleted_at', null).eq('status', 'PASS'),
      ])

      const siteCounts: Record<string, number> = {}
      for (const row of (siteRes.data ?? []) as Pick<Tender, 'source_site'>[]) {
        siteCounts[row.source_site] = (siteCounts[row.source_site] ?? 0) + 1
      }

      const kwCounts: Record<string, number> = {}
      for (const row of (kwRes.data ?? []) as Pick<Tender, 'keywords_matched'>[]) {
        for (const kw of row.keywords_matched ?? []) {
          kwCounts[kw] = (kwCounts[kw] ?? 0) + 1
        }
      }

      const lastRun = ((runsRes.data ?? [])[0] ?? null) as ScrapeRun | null

      return {
        total_tenders: totalRes.count ?? 0,
        new_today: todayRes.count ?? 0,
        sites_monitored: Object.keys(siteCounts).length,
        last_run_at: lastRun?.started_at ?? null,
        last_run_status: lastRun?.status ?? null,
        tenders_by_site: Object.entries(siteCounts).map(([site, count]) => ({ site, count })).sort((a, b) => b.count - a.count).slice(0, 10),
        tenders_by_keyword: Object.entries(kwCounts).map(([keyword, count]) => ({ keyword, count })).sort((a, b) => b.count - a.count),
      }
    },
    refetchInterval: 60_000,
  })
}

export function useScrapeRuns(limit = 10) {
  return useQuery({
    queryKey: ['scrape-runs', limit],
    queryFn: async () => {
      const { data, error } = await supabase.from('scrape_runs').select('*').is('deleted_at', null).order('started_at', { ascending: false }).limit(limit)
      if (error) throw new Error(error.message)
      return (data ?? []) as ScrapeRun[]
    },
    refetchInterval: 30_000,
  })
}
