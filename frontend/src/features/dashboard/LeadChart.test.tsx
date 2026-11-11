import { useRef } from 'react'
import { fireEvent, render, screen } from '@testing-library/react'
import type { ChartData } from 'chart.js'
import { LeadChart } from './LeadChart'
import type { DashboardData } from './types'

// The real chart needs a canvas. Capture what LeadChart hands to it instead: the axis text and every line's values.
let seen: ChartData<'line'> | null = null
let plugins: { id: string; beforeDatasetsDraw?: (c: unknown, a: unknown, o: unknown) => void }[] = []
let pluginOpts: Record<string, unknown> = {}
vi.mock('react-chartjs-2', () => ({
  // like the real library: the plugins an instance was created with are the only ones it ever uses
  Line: ({ data, plugins: p, options }: { data: ChartData<'line'>; plugins: typeof plugins; options: { plugins: Record<string, unknown> } }) => {
    const created = useRef(p)
    seen = data
    pluginOpts = options.plugins
    plugins = created.current
    return null
  },
}))

const base: DashboardData = {
  labels: ['11-06', '11-13', '11-20'], // week 1 (6 Nov) is already over on 11 Nov
  cash_rules: [100, 90, 80],
  rulesFromSavedRun: false,
  ml: { cash_ml: [101, 91, 81], p10: [95, 85, 75], p90: [105, 95, 85] },
  receipts: null,
  actuals: null,
  floor: null,
  ar: [],
  ap: [],
  inflows: [],
  outflows: [],
  streams: {},
  outflowStreams: {},
  kpis: {
    opening_cash: 74000,
    ending_cash: 80,
    lowest_cash: 80,
    lowest_week: '11-20',
    total_inflow: 0,
    total_outflow: 0,
    total_ar: 0,
    total_ap: 0,
    net_change: 0,
    avg_weekly_net: 0,
    as_of: '2026-11-06',
  },
}
const line = (name: string) => seen!.datasets.find((d) => d.label === name)!.data

describe('LeadChart axis and lines', () => {
  it('without actuals (Zoho off): plain forecast weeks, in order, nothing undefined, no green line', () => {
    render(<LeadChart d={base} mlPending={false} mlFailed={false} />)
    expect(seen!.labels).toEqual(['Nov 6', 'Nov 13', 'Nov 20'])
    expect(line('Rules timing')).toEqual([100, 90, 80])
    expect(seen!.datasets.some((d) => d.label?.startsWith('Actual'))).toBe(false)
  })
  it('with actuals: today sits between the Fridays and every line starts at its actual balance', () => {
    const actuals = {
      startDate: '2026-10-28',
      points: [
        { date: '2026-11-06', balance: 54, kind: 'week_end' as const },
        { date: '2026-11-11', balance: 60, kind: 'today' as const },
      ],
    }
    render(<LeadChart d={{ ...base, actuals }} mlPending={false} mlFailed={false} />)
    expect(seen!.labels).toEqual(['Nov 6', 'Nov 11', 'Nov 13', 'Nov 20'])
    expect(line('Rules timing')).toEqual([100, 60, 90, 80]) // 6 Nov: the earlier forecast; from 11 Nov: today's actual
    expect(line('ML timing')).toEqual([101, 60, 91, 81])
    expect(line('Actual cash (Zoho books)')).toEqual([54, 60, null, null])
    expect(line('Likely range (ML timing)')).toEqual([null, 60, 95, 85]) // no band for the week already over
  })

  it('draws the grey assumption zone from the right slot, and one slot later when the today slot is added', () => {
    // 20 weeks; from week 8 on both lines are equal with a zero-width band (no document left to time)
    const labels = Array.from({ length: 20 }, (_, i) => new Date(Date.UTC(2026, 10, 6 + 7 * i)).toISOString().slice(5, 10))
    const rules = labels.map((_, i) => 100 - i)
    const ml = {
      cash_ml: rules.map((v, i) => (i < 8 ? v + 1 : v)),
      p10: rules.map((v, i) => (i < 8 ? v - 5 : v)),
      p90: rules.map((v, i) => (i < 8 ? v + 5 : v)),
    }
    const zoneStart = () => {
      const xs: number[] = []
      const chart = {
        data: { labels: new Array(14).fill('x') },
        ctx: { save() {}, restore() {}, fillRect: (x: number) => xs.push(x), fillText() {}, fillStyle: '', font: '', textAlign: '', textBaseline: '' },
        chartArea: { left: 0, right: 500, top: 0, bottom: 100 },
        scales: { x: { getPixelForValue: (i: number) => i * 10 } },
      }
      plugins.find((p) => p.id === 'assumptionZone')!.beforeDatasetsDraw!(chart, {}, pluginOpts.assumptionZone)
      return xs[0] === undefined ? null : (xs[0] + 5) / 10 // slot index the zone starts at
    }
    render(<LeadChart d={{ ...base, labels, cash_rules: rules, ml }} mlPending={false} mlFailed={false} />)
    expect(zoneStart()).toBe(8)
    const actuals = { startDate: 'x', points: [{ date: '2026-11-11', balance: 6, kind: 'today' as const }] }
    render(<LeadChart d={{ ...base, labels, cash_rules: rules, ml, actuals }} mlPending={false} mlFailed={false} />)
    expect(zoneStart()).toBe(9) // today's slot sits before week 2
  })

  it('52w view of your real data shape: lines differ until week 28, so the grey zone starts at slot 28 (and is off screen in 13w)', () => {
    const labels = Array.from({ length: 52 }, (_, i) => new Date(Date.UTC(2026, 10, 6 + 7 * i)).toISOString().slice(5, 10))
    const rules = labels.map((_, i) => 100 - i)
    const apart = (i: number) => i < 28 // real run: a 32K timing difference sits in weeks 24-27, equal from 28 on
    const ml = {
      cash_ml: rules.map((v, i) => (apart(i) ? v + 5 : v)),
      p10: rules.map((v, i) => (apart(i) ? v - 5 : v)),
      p90: rules.map((v, i) => (apart(i) ? v + 5 : v)),
    }
    const zoneAt = (slots: number) => {
      const xs: number[] = []
      const chart = {
        data: { labels: new Array(slots).fill('x') },
        ctx: { save() {}, restore() {}, fillRect: (x: number) => xs.push(x), fillText() {}, fillStyle: '', font: '', textAlign: '', textBaseline: '' },
        chartArea: { left: 0, right: 500, top: 0, bottom: 100 },
        scales: { x: { getPixelForValue: (i: number) => i * 10 } },
      }
      plugins.find((p) => p.id === 'assumptionZone')!.beforeDatasetsDraw!(chart, {}, pluginOpts.assumptionZone)
      return xs[0] === undefined ? null : (xs[0] + 5) / 10
    }
    render(<LeadChart d={{ ...base, labels, cash_rules: rules, ml }} mlPending={false} mlFailed={false} />)
    expect(zoneAt(13)).toBeNull() // 13w: nothing to grey out yet
    fireEvent.click(screen.getByText('52w'))
    expect(seen!.labels).toHaveLength(52)
    expect(zoneAt(52)).toBe(28)
  })
})
