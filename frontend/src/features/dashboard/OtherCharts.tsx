import { useMemo, useState } from 'react'
import { Bar, Chart, Line } from 'react-chartjs-2'
import type { ChartData, Plugin } from 'chart.js'
import { RangeToggle } from '@/features/dashboard/RangeToggle'
import { assumptionPlugin, assumptionStart } from '@/features/dashboard/assumption'
import type { DashboardData } from '@/features/dashboard/types'
import { dlabel } from '@/shared/format'
import { alpha, useChartTokens } from '@/shared/chart/tokens'
import { baseOptions } from '@/shared/chart/base'
export function ArApChart({ d }: { d: DashboardData }) {
  const t = useChartTokens()
  const [n, setN] = useState(13)
  const labels = useMemo(() => d.labels.map(dlabel).slice(0, n), [d, n])
  const options = useMemo(() => baseOptions(t), [t])
  const data = {
    labels,
    datasets: [
      {
        label: 'Receivables (money to come in)',
        data: d.ar.slice(0, n),
        borderColor: t.inC,
        backgroundColor: alpha(t.inC, 0.12),
        fill: true,
        borderWidth: 2.2,
        pointRadius: 0,
        tension: 0.3,
      },
      {
        label: 'Payables (money to pay out)',
        data: d.ap.slice(0, n),
        borderColor: t.outC,
        backgroundColor: alpha(t.outC, 0.1),
        fill: true,
        borderWidth: 2.2,
        pointRadius: 0,
        tension: 0.3,
      },
    ],
  }
  return (
    <article className="card">
      <div className="card-head">
        <div>
          <h2>Receivables and payables</h2>
          <p className="sub">Customer money still to arrive vs vendor money still to pay out.</p>
        </div>
        <div className="controls">
          <RangeToggle value={n} onChange={setN} />
        </div>
      </div>
      <div className="chart">
        <Line data={data} options={options} />
      </div>
    </article>
  )
}

export function InOutChart({ d }: { d: DashboardData }) {
  const t = useChartTokens()
  const [n, setN] = useState(13)
  const labels = useMemo(() => d.labels.map(dlabel), [d])
  const from = useMemo(() => assumptionStart(d), [d])
  const options = useMemo(() => {
    const o = baseOptions(t)
    if (o.scales?.x) o.scales.x.stacked = true
    if (o.scales?.y) o.scales.y.stacked = true
    return o
  }, [t])
  const plugins = useMemo(() => [assumptionPlugin(t, from)], [t, from])
  const cut = (a: number[]) => a.slice(0, n)
  const bar = {
    type: 'bar' as const,
    order: 1,
    borderRadius: 2,
    barPercentage: 0.7,
    categoryPercentage: 0.8,
    stack: 's',
  }
  const data = {
    labels: labels.slice(0, n),
    datasets: [
      { ...bar, label: 'Cash receipts', data: cut(d.inflows), backgroundColor: t.inC },
      { ...bar, label: 'Cash payments', data: cut(d.outflows.map((v) => -v)), backgroundColor: t.outC },
      {
        type: 'line' as const,
        label: 'Net (receipts − payments)',
        data: cut(d.inflows.map((v, i) => v - (d.outflows[i] ?? 0))),
        borderColor: t.text,
        backgroundColor: t.text,
        borderWidth: 2,
        pointRadius: n <= 13 ? 3 : 0,
        pointHoverRadius: 5,
        tension: 0.25,
        stack: 'net',
        order: 0, // lower order draws on top of the bars
      },
    ],
  } as unknown as ChartData<'bar'>
  return (
    <article className="card">
      <div className="card-head">
        <div>
          <h2>Cash receipts and cash payments</h2>
          <p className="sub">Receipts go up, payments go down. The line is the net for the week.</p>
        </div>
        <div className="controls">
          <RangeToggle value={n} onChange={setN} />
        </div>
      </div>
      <div className="chart">
        <Chart key={from ?? 'none'} type="bar" data={data} options={options} plugins={plugins as Plugin<'bar'>[]} />
      </div>
      <div className="legend">
        <span>
          <i className="box" style={{ background: t.inC }} />
          Cash receipts
        </span>
        <span>
          <i className="box" style={{ background: t.outC }} />
          Cash payments
        </span>
        <span>
          <i className="box" style={{ background: t.text }} />
          Net for the week
        </span>
      </div>
    </article>
  )
}

export function StreamsChart({ d }: { d: DashboardData }) {
  const t = useChartTokens()
  const [n, setN] = useState(13)
  const labels = useMemo(() => d.labels.map(dlabel).slice(0, n), [d, n])
  const options = useMemo(() => baseOptions(t, { stacked: true }), [t])
  const cols: Record<string, string> = { SERVPRO: t.s1, Amazon: t.s2, 'Other Resellers': t.s3, 'A/R Collection': t.s4 }
  const names = ['A/R Collection', 'SERVPRO', 'Other Resellers', 'Amazon'].filter((k) => d.streams[k])
  const data = {
    labels,
    datasets: names.map((k) => ({
      label: k,
      data: d.streams[k].slice(0, n),
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
          <h2>Where revenue comes from</h2>
          <p className="sub">Weekly inflows by source.</p>
        </div>
        <div className="controls">
          <RangeToggle value={n} onChange={setN} />
        </div>
      </div>
      <div className="chart">
        <Bar data={data} options={options} />
      </div>
      <div className="legend">
        {names.map((k) => (
          <span key={k}>
            <i className="box" style={{ background: cols[k] }} />
            {k}
          </span>
        ))}
      </div>
    </section>
  )
}
