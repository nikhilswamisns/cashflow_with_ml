import { renderHook, waitFor } from '@testing-library/react'
import { QueryClientProvider } from '@tanstack/react-query'
import type { ReactNode } from 'react'
import { useDashboard } from './hooks'
import { newClient, stubApi } from '@/test/utils'

const analytics = {
  labels: ['10-30', '11-06'],
  cash_trajectory: [-1, -2],
  inflows: [1, 2],
  outflows: [1, 2],
  revenue_streams: { SERVPRO: [0, 0] },
  ar_ap: { ar_trajectory: [1, 1], ap_trajectory: [2, 2] },
  kpis: {
    opening_cash: 10,
    ending_cash: 20,
    lowest_cash: -5,
    lowest_week: '10-30',
    total_inflow: 3,
    total_outflow: 2,
    total_ar: 1,
    total_ap: 2,
    net_change: 10,
    avg_weekly_net: 1,
    as_of: '2026-10-30',
  },
}
const compare = { ending_cash_rules: [-10, -20], ending_cash_ml: [5, 6], bands: { p10: [0, 0], p90: [9, 9] } }
const outlook = { documents: [1, 1], run_rate: [2, 2], forecast_added: [3, 3] }

const wrap = ({ children }: { children: ReactNode }) => (
  <QueryClientProvider client={newClient()}>{children}</QueryClientProvider>
)
afterEach(() => vi.unstubAllGlobals())

describe('useDashboard', () => {
  it('takes the blue line from /compare (rules only), never from the saved run', async () => {
    stubApi({
      'GET /runs/r1/analytics': analytics,
      'GET /ml/runs/r1/compare': compare,
      'GET /ml/runs/r1/receipts-outlook': outlook,
    })
    const { result } = renderHook(() => useDashboard('r1'), { wrapper: wrap })
    await waitFor(() => expect(result.current.data?.ml).toBeTruthy())
    expect(result.current.data?.cash_rules).toEqual([-10, -20])
    expect(result.current.data?.rulesFromSavedRun).toBe(false)
    expect(result.current.data?.receipts).toEqual({ docs: [1, 1], runrate: [2, 2], forecast: [3, 3] })
    expect(result.current.data?.floor).toBeNull() // the server has no minimum-cash setting
  })
  it('falls back to the saved run, and says so, when /compare is not available (older runs)', async () => {
    stubApi({ 'GET /runs/old/analytics': analytics })
    const { result } = renderHook(() => useDashboard('old'), { wrapper: wrap })
    await waitFor(() => expect(result.current.mlFailed).toBe(true))
    expect(result.current.data?.cash_rules).toEqual([-1, -2])
    expect(result.current.data?.rulesFromSavedRun).toBe(true)
    expect(result.current.data?.ml).toBeNull()
    expect(result.current.data?.receipts).toBeNull()
  })
  it('does nothing until a run is selected', () => {
    const f = stubApi({})
    const { result } = renderHook(() => useDashboard(''), { wrapper: wrap })
    expect(result.current.data).toBeUndefined()
    expect(f).not.toHaveBeenCalled()
  })
})
