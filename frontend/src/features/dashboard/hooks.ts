import { useMemo } from 'react'
import { useQueries, useQuery } from '@tanstack/react-query'
import { fetchActuals, fetchAnalytics, fetchMl, fetchReceipts, fetchTrack } from './api'
import type { DashboardData } from '@/features/dashboard/types'
// Three calls: analytics (fast), receipts (fast), compare (slow the first time). The page shows as soon as
// analytics is in. The cash chart waits for compare, because the saved run's line can already be ML-timed.
export function useDashboard(runId: string) {
  const on = !!runId
  const [an, rc, ml, ac] = useQueries({
    queries: [
      { queryKey: ['analytics', runId], queryFn: () => fetchAnalytics(runId), enabled: on },
      { queryKey: ['receipts', runId], queryFn: () => fetchReceipts(runId), enabled: on, retry: false },
      { queryKey: ['ml', runId], queryFn: () => fetchMl(runId), enabled: on, retry: false, staleTime: 5 * 60_000 },
      {
        queryKey: ['actuals', runId],
        queryFn: () => fetchActuals(runId),
        enabled: on,
        retry: false,
        staleTime: 5 * 60_000,
      },
    ],
  })
  const a = an.data
  const data = useMemo<DashboardData | undefined>(
    () =>
      a && {
        labels: a.labels,
        kpis: a.kpis,
        cash_rules: ml.data ? ml.data.rules : a.cash_trajectory,
        rulesFromSavedRun: !ml.data,
        ml: ml.data?.ml ?? null,
        receipts: rc.data ?? null,
        actuals: ac.data ?? null,
        floor: null, // no minimum-cash setting exists on the server yet
        ar: a.ar_ap.ar_trajectory,
        ap: a.ar_ap.ap_trajectory,
        inflows: a.inflows,
        outflows: a.outflows,
        streams: a.revenue_streams,
      },
    [a, ml.data, rc.data, ac.data],
  )
  return {
    data,
    error: an.error,
    mlPending: ml.isPending && on,
    mlFailed: ml.isError,
    receiptsFailed: rc.isError,
    receiptsPending: rc.isPending && on,
  }
}

export const useTrack = () =>
  useQuery({ queryKey: ['track'], queryFn: fetchTrack, staleTime: 5 * 60_000, retry: false })
