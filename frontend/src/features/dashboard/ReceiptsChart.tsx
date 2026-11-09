import { useMemo, useState } from 'react'
import { Line } from 'react-chartjs-2'
import type { DashboardData } from '@/features/dashboard/types'
import { dlabel, kfmt, sum } from '@/shared/format'
import { alpha, useChartTokens } from '@/shared/chart/tokens'
import { baseOptions } from '@/shared/chart/base'

type Key = 'booked' | 'reseller' | 'forecast'

export function ReceiptsChart({ d, pending }: { d: DashboardData; pending: boolean }) {
  const t = useChartTokens()
  const [on, setOn] = useState<Record<Key, boolean>>({ booked: true, reseller: true, forecast: true })
  const labels = useMemo(() => d.labels.map(dlabel), [d])
  const docs = d.receipts?.docs ?? []
  const runrate = d.receipts?.runrate ?? []
  const forecast = d.receipts?.forecast ?? []
  const sets: [Key, string, number[], string][] = [
    ['booked', 'Invoiced and ordered', docs, t.booked],
    ['reseller', 'Regular reseller income', runrate, t.reseller],
    ['forecast', 'Forecast new sales', forecast, t.forecast],
  ]
  const data = {
    labels,
    datasets: sets.map(([k, l, arr, c]) => ({
      label: l,
      data: arr,
      hidden: !on[k],
      borderColor: c,
      backgroundColor: alpha(c, 0.62),
      borderWidth: 1.8,
      fill: true,
      cubicInterpolationMode: 'monotone' as const,
      pointRadius: 0,
      pointHoverRadius: 4,
      pointHoverBackgroundColor: c,
    })),
  }
  const options = useMemo(() => {
    const o = baseOptions(t, { stacked: true })
    if (o.scales?.y) o.scales.y.min = 0 // smoothing must never dip below zero
    return o
  }, [t])
  const tot = sum(docs) + sum(runrate) + sum(forecast)
  const steady = Math.round(((sum(docs) + sum(runrate)) / tot) * 100)

  if (!d.receipts) {
    return (
      <section className="card">
        <div className="card-head">
          <div>
            <h2>Expected receipts</h2>
            <p className="sub">Cash in per week, split by how certain it is. No costs.</p>
          </div>
        </div>
        <div className="chart chart-wait">
          <span>
            {pending
              ? 'Loading…'
              : 'Expected receipts are not available for this run (the revenue forecast files may be missing on the server).'}
          </span>
        </div>
      </section>
    )
  }
  return (
    <section className="card">
      <div className="card-head">
        <div>
          <h2>Expected receipts</h2>
          <p className="sub">Cash in per week, split by how certain it is. No costs.</p>
        </div>
        <div className="chips-row">
          {sets.map(([k, l, arr, c]) => (
            <button
              key={k}
              className={`chip ${on[k] ? 'on' : ''}`}
              aria-pressed={on[k]}
              onClick={() => setOn({ ...on, [k]: !on[k] })}
            >
              <i style={{ background: c }} />
              {l}
              <b>{kfmt(sum(arr))}</b>
            </button>
          ))}
        </div>
      </div>
      <div className="chart">
        <Line data={data} options={options} />
      </div>
      <p className="insight">
        Of <b>{kfmt(tot)}</b> expected in 52 weeks, only <b>{steady}%</b> is booked or a steady reseller run-rate.{' '}
        <b>{Math.round((sum(forecast) / tot) * 100)}%</b> depends on new sales that have not happened yet, and from
        about week 19 the bars are almost all forecast.
      </p>
    </section>
  )
}
