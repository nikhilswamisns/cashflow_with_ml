import { render, screen } from '@testing-library/react'
import { Kpis } from './Kpis'
import { FundingGap } from './FundingGap'
import { assumptionStart } from './assumption'
import type { DashboardData } from './types'

const base: DashboardData = {
  labels: ['10-30', '11-06', '11-13'],
  cash_rules: [10, -50, 30],
  rulesFromSavedRun: false,
  ml: null,
  receipts: null,
  floor: null,
  ar: [],
  ap: [],
  inflows: [],
  outflows: [],
  streams: {},
  kpis: {
    opening_cash: 74096.81,
    ending_cash: 644926.38,
    lowest_cash: -201427.9,
    lowest_week: '12-25',
    total_inflow: 0,
    total_outflow: 0,
    total_ar: 330355.8,
    total_ap: 307708.18,
    net_change: 570829.57,
    avg_weekly_net: 0,
    as_of: '2026-10-30',
  },
}

describe('Kpis', () => {
  it('shows four cards: book cash, lowest week with date and line, A/R, A/P', () => {
    render(<Kpis d={base} syncedLabel="Run created Oct 30, 9:00 AM" />)
    expect(screen.getByText('Book cash (Zoho)')).toBeInTheDocument()
    expect(screen.getByText('$74,097')).toBeInTheDocument()
    expect(screen.getByText('Zoho book balance · Oct 30')).toBeInTheDocument()
    expect(screen.getByText('−$50')).toBeInTheDocument()
    expect(screen.getByText('Week ending Nov 6, 2026 · rule-date line')).toBeInTheDocument()
    expect(screen.getByText('$330,356')).toBeInTheDocument()
    expect(screen.getByText('You owe vendors. A/R covers it 1.07×.')).toBeInTheDocument()
  })
  it('rolls the year over in December', () => {
    const d = {
      ...base,
      labels: ['12-25', '01-01', '01-08'],
      cash_rules: [5, 6, -1],
      kpis: { ...base.kpis, as_of: '2026-12-25' },
    }
    render(<Kpis d={d} />)
    expect(screen.getByText(/Week ending Jan 8, 2027/)).toBeInTheDocument()
  })
})

describe('FundingGap', () => {
  it('peak need is buffer minus the lowest cash, and counts weeks below zero', () => {
    render(<FundingGap d={{ ...base, floor: 25 }} />)
    expect(screen.getByText('$75')).toBeInTheDocument()
    expect(screen.getByText('1')).toBeInTheDocument()
  })
  it('shows $0 and "no gap" when cash stays above the buffer', () => {
    render(<FundingGap d={{ ...base, cash_rules: [100, 200, 300], floor: 50 }} />)
    expect(screen.getByText('$0')).toBeInTheDocument()
    expect(screen.getByText(/No gap/)).toBeInTheDocument()
  })
})

describe('assumptionStart', () => {
  const ml = (cash_ml: number[], p10: number[], p90: number[]) => ({ ...base, ml: { cash_ml, p10, p90 } })
  it('is the first week after which both lines match and the band has no width', () => {
    expect(assumptionStart(ml([10, -40, 30], [0, -60, 30], [0, -20, 30]))).toBe(2)
  })
  it('is null without ML, or when the lines differ in the last week', () => {
    expect(assumptionStart(base)).toBeNull()
    expect(assumptionStart(ml([10, -50, 99], [0, 0, 0], [0, 0, 0]))).toBeNull()
  })
})
