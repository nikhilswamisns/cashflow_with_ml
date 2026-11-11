import { useMemo, useState } from 'react'
import { Bar } from 'react-chartjs-2'
import type { DashboardData } from '@/features/dashboard/types'
import { RangeToggle } from '@/features/dashboard/RangeToggle'
import { useChartTokens } from '@/shared/chart/tokens'
import { baseOptions } from '@/shared/chart/base'
import { dlabel, usd } from '@/shared/format'

const ORDER = [
  'Inventory',
  'Freight & duty',
  'Payroll',
  'Fulfilment & Amazon',
  'Marketing & ads',
  'Loans & interest',
  'Other',
]

/** Weekly outflows stacked by what the money is for; the legend shows each group's share of the chosen range. */
export function OutflowChart({ d }: { d: DashboardData }) {
  const t = useChartTokens()
  const [n, setN] = useState(13)
  const labels = useMemo(() => d.labels.map(dlabel).slice(0, n), [d, n])
  const options = useMemo(() => baseOptions(t, { stacked: true }), [t])
  const cols: Record<string, string> = {
    Inventory: t.s4,
    'Freight & duty': t.reseller,
    Payroll: t.s1,
    'Fulfilment & Amazon': t.outC,
    'Marketing & ads': t.s2,
    'Loans & interest': t.booked,
    Other: t.s3,
  }
  const names = ORDER.filter((k) => d.outflowStreams[k])
  if (!names.length) return null
  const totals = names.map((k) => d.outflowStreams[k].slice(0, n).reduce((s, v) => s + v, 0))
  const grand = totals.reduce((s, v) => s + v, 0)
  const data = {
    labels,
    datasets: names.map((k) => ({
      label: k,
      data: d.outflowStreams[k].slice(0, n),
      backgroundColor: cols[k],
      stack: 's',
      borderRadius: 1,
      barPercentage: 0.78,
      categoryPercentage: 0.86,
    })),
  }
  return (
    <section className="card">
      <div className="card-head">
        <div>
          <h2>Where cash goes</h2>
          <p className="sub">Weekly outflows by what the money is for.</p>
        </div>
        <div className="controls">
          <RangeToggle value={n} onChange={setN} />
        </div>
      </div>
      <div className="chart">
        <Bar data={data} options={options} />
      </div>
      <div className="legend">
        {names.map((k, i) => (
          <span key={k} title={usd(totals[i])}>
            <i className="box" style={{ background: cols[k] }} />
            {k} {grand > 0 ? `${Math.round((totals[i] / grand) * 100)}%` : ''}
          </span>
        ))}
      </div>
    </section>
  )
}
