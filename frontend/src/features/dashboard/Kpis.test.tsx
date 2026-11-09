import { render, screen } from '@testing-library/react'
import { Kpis } from './Kpis'
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
  it('shows the five cards with formatted amounts and a sentence each', () => {
    render(<Kpis d={base} />)
    expect(screen.getByText('$74,097')).toBeInTheDocument()
    expect(screen.getByText('−$201,428')).toBeInTheDocument()
    expect(screen.getByText('$330,356')).toBeInTheDocument()
    expect(screen.getByText(/Week ending Nov 6\. Below zero for 1 weeks\./)).toBeInTheDocument()
    expect(screen.getByText('You owe vendors. A/R covers it 1.07×.')).toBeInTheDocument()
  })
  it('says "Down" when cash falls over the year', () => {
    render(<Kpis d={{ ...base, kpis: { ...base.kpis, net_change: -1000 } }} />)
    expect(screen.getByText('Down $1,000 on today.')).toBeInTheDocument()
  })
})
