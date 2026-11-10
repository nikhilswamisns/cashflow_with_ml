import { render, screen } from '@testing-library/react'
import { QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import { ActionsCard } from './ActionsCard'
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
    count: 12,
    total: 50000,
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

describe('ActionsCard', () => {
  it('shows overdue invoices with days late and bills with their status, plus the totals', async () => {
    stubApi({ 'GET /runs/r1/actions': actions })
    render(wrap(<ActionsCard />))
    expect(await screen.findByText('Acme')).toBeInTheDocument()
    expect(screen.getByText('5 days late')).toBeInTheDocument()
    expect(screen.getByText('12 overdue · $50,000')).toBeInTheDocument()
    expect(screen.getByText('1 day late')).toBeInTheDocument()
    expect(screen.getByText('in 3 days')).toBeInTheDocument()
    expect(screen.getByText(/2 due · \$3,500 · 1 already late \(\$500\)/)).toBeInTheDocument()
    expect(screen.getByText('+ 11 more overdue')).toBeInTheDocument()
  })
  it('renders nothing for a run without stored open items', async () => {
    stubApi({})
    const { container } = render(wrap(<ActionsCard />))
    await new Promise((r) => setTimeout(r, 50))
    expect(container.querySelector('section')).toBeNull()
  })
})
