import { render, screen } from '@testing-library/react'
import { QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import { WorkingCapitalPage } from './WorkingCapitalPage'
import { newClient, stubApi } from '@/test/utils'

vi.mock('@/features/runs/RunProvider', () => ({ useRun: () => ({ runId: 'r1' }) }))
afterEach(() => vi.unstubAllGlobals())
const wrap = (ui: React.ReactNode) => (
  <QueryClientProvider client={newClient()}>
    <MemoryRouter>{ui}</MemoryRouter>
  </QueryClientProvider>
)
const labels = ['Not due', '0-30', '31-60', '61-90', '90+']
const aging = (amts: number[]) => ({
  total: amts.reduce((a, b) => a + b, 0),
  count: 3,
  missing_due_date: 0,
  buckets: labels.map((label, i) => ({ label, amount: amts[i], count: 1, share: 0.2 })),
})
const shares = {
  total: 1000,
  top: [{ party: 'SERVPRO - Corporate', amount: 600, share: 0.6 }],
  top_share: 0.6,
  focus_name: 'SERVPRO',
  focus_amount: 600,
  focus_share: 0.6,
}
const wc = {
  as_of: '2026-11-09',
  window_days: 90,
  ar: aging([900, 50, 30, 10, 10]),
  ap: aging([400, 100, 0, 0, 0]),
  dso: 45.4,
  dpo: null,
  sales_90: 90000,
  cogs_90: null,
  flows_available: true,
  concentration: { ar: shares, sales: null },
}

describe('WorkingCapitalPage', () => {
  it('shows DSO, n/a for an unknown DPO, aging buckets and concentration', async () => {
    stubApi({ 'GET /runs/r1/working-capital': wc })
    render(wrap(<WorkingCapitalPage />))
    expect(await screen.findByText('45 days')).toBeInTheDocument()
    expect(screen.getByText('n/a')).toBeInTheDocument()
    expect(screen.getByText('$1,000')).toBeInTheDocument() // open A/R
    expect(screen.getAllByText('61-90 days late').length).toBe(2)
    expect(screen.getAllByText('60%').length).toBeGreaterThan(0)
    expect(screen.getByText(/Zoho P&L has no Cost of Goods Sold/)).toBeInTheDocument()
    expect(screen.getByText(/Zoho could not be read for the last 90 days/)).toBeInTheDocument()
  })
  it('says so when the run has no open items stored', async () => {
    stubApi({})
    render(wrap(<WorkingCapitalPage />))
    expect(await screen.findByText('No working capital for this run')).toBeInTheDocument()
  })
})
