import { render, screen } from '@testing-library/react'
import { QueryClientProvider } from '@tanstack/react-query'
import { AccuracyCard } from './AccuracyCard'
import { newClient, stubApi } from '@/test/utils'

afterEach(() => vi.unstubAllGlobals())
const wrap = (ui: React.ReactNode) => <QueryClientProvider client={newClient()}>{ui}</QueryClientProvider>
const track = (
  rows: object[],
  summary: { weeks_scored: number; avg_miss_rules: number | null; avg_miss_ml: number | null } = {
    weeks_scored: 0,
    avg_miss_rules: null,
    avg_miss_ml: null,
  },
) => ({
  rows,
  summary,
  horizon_weeks: 2,
  rule: 'x',
})

describe('AccuracyCard', () => {
  it('lists completed weeks with the gap for each line and which was closer', async () => {
    stubApi({
      'GET /ml/forecast-track': track(
        [
          {
            week_ending: '2026-11-06',
            rules: -100010,
            ml: 85090,
            actual: 53898,
            gap_rules: 153908,
            gap_ml: -31192,
            closer: 'ml',
            run_created: 'x',
          },
          { week_ending: '2026-11-13', rules: -21620, ml: 5000, actual: null, run_created: 'x' },
        ],
        { weeks_scored: 1, avg_miss_rules: 153908, avg_miss_ml: 31192 },
      ),
    })
    render(wrap(<AccuracyCard />))
    expect(await screen.findByText('Nov 6, 2026')).toBeInTheDocument()
    expect(screen.getByText('$53,898')).toBeInTheDocument()
    expect(screen.getByText('+$153,908')).toBeInTheDocument()
    expect(screen.getByText('−$31,192')).toBeInTheDocument()
    expect(screen.getByText('ML timing')).toBeInTheDocument()
    expect(screen.queryByText('Nov 13, 2026')).toBeNull() // not completed yet
    expect(screen.getByText(/missed by/)).toBeInTheDocument()
  })
  it('says when the first comparison will appear if no week has finished', async () => {
    stubApi({
      'GET /ml/forecast-track': track([{ week_ending: '2026-11-13', rules: 1, ml: 2, actual: null, run_created: 'x' }]),
    })
    render(wrap(<AccuracyCard />))
    expect(await screen.findByText(/first comparison appears after the week ending Nov 13, 2026/)).toBeInTheDocument()
  })
  it('renders nothing when the server cannot read Zoho', async () => {
    stubApi({})
    const { container } = render(wrap(<AccuracyCard />))
    await new Promise((r) => setTimeout(r, 50))
    expect(container.querySelector('section')).toBeNull()
  })
})
