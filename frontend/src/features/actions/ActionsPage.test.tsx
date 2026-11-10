import { render, screen } from '@testing-library/react'
import { QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import { ActionsPage } from './ActionsPage'
import { newClient, stubApi } from '@/test/utils'

vi.mock('@/features/runs/RunProvider', () => ({ useRun: () => ({ runId: 'r1' }) }))
afterEach(() => vi.unstubAllGlobals())
const wrap = (ui: React.ReactNode) => (
  <QueryClientProvider client={newClient()}>
    <MemoryRouter>{ui}</MemoryRouter>
  </QueryClientProvider>
)
const actions = {
  as_of: '2026-11-09',
  window_days: 14,
  invoices: {
    count: 2,
    total: 20500,
    items: [{ number: 'INV-1', party: 'Acme', due_date: '2026-11-04', days_overdue: 5, amount: 20000 }],
  },
  bills: {
    count: 2,
    total: 3500,
    overdue_count: 1,
    overdue_total: 500,
    items: [
      { number: 'B-1', party: 'Vendor A', due_date: '2026-11-08', days_overdue: 1, days_until_due: 0, amount: 500 },
      { number: 'B-2', party: 'Vendor B', due_date: '2026-11-12', days_overdue: 0, days_until_due: 3, amount: 3000 },
    ],
  },
}

describe('ActionsPage', () => {
  it('shows the totals, overdue invoices with days late, and bills with their status', async () => {
    stubApi({ 'GET /runs/r1/actions': actions })
    render(wrap(<ActionsPage />))
    expect(await screen.findByText('Acme')).toBeInTheDocument()
    expect(screen.getByText('$20,500')).toBeInTheDocument() // overdue invoices tile
    expect(screen.getByText('2 invoices to chase')).toBeInTheDocument()
    expect(screen.getByText('1 bill past the due date')).toBeInTheDocument()
    expect(screen.getByText('5 days late')).toBeInTheDocument()
    expect(screen.getByText('1 day late')).toBeInTheDocument()
    expect(screen.getByText('in 3 days')).toBeInTheDocument()
    expect(screen.getByText('+ 1 more')).toBeInTheDocument() // 2 overdue invoices, 1 listed
  })
  it('says so when the run has no open items stored', async () => {
    stubApi({})
    render(wrap(<ActionsPage />))
    expect(await screen.findByText('No actions for this run')).toBeInTheDocument()
  })
})
