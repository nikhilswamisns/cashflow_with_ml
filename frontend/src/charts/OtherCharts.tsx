import { useMemo } from 'react'
import { Bar, Line } from 'react-chartjs-2'
import type { DashboardData } from '../data/types'
import { dlabel } from '../lib/format'
import { alpha, useChartTokens } from './tokens'
import { baseOptions } from './base'

export function ArApChart({ d }: { d: DashboardData }) {
  const t = useChartTokens()
  const labels = useMemo(() => d.labels.map(dlabel), [d])
  const options = useMemo(() => baseOptions(t), [t])
  const data = {
    labels,
    datasets: [
      { label: 'Receivables (money to come in)', data: d.ar, borderColor: t.inC, backgroundColor: alpha(t.inC, 0.12), fill: true, borderWidth: 2.2, pointRadius: 0, tension: 0.3 },
      { label: 'Payables (money to pay out)', data: d.ap, borderColor: t.outC, backgroundColor: alpha(t.outC, 0.1), fill: true, borderWidth: 2.2, pointRadius: 0, tension: 0.3 },
    ],
  }
  return (
    <article className="card">
      <div className="card-head"><div><h2>Receivables and payables</h2><p className="sub">Customer money still to arrive vs vendor money still to pay out.</p></div></div>
      <div className="chart"><Line data={data} options={options} /></div>
    </article>
  )
}

export function InOutChart({ d }: { d: DashboardData }) {
  const t = useChartTokens()
  const labels = useMemo(() => d.labels.map(dlabel), [d])
  const options = useMemo(() => baseOptions(t), [t])
  const bar = { borderRadius: 2, barPercentage: 0.8, categoryPercentage: 0.8 }
  const data = {
    labels,
    datasets: [
      { label: 'Money in', data: d.inflows, backgroundColor: t.inC, ...bar },
      { label: 'Money out', data: d.outflows, backgroundColor: t.outC, ...bar },
    ],
  }
  return (
    <article className="card">
      <div className="card-head"><div><h2>Inflows and outflows</h2><p className="sub">Weekly money in vs money out.</p></div></div>
      <div className="chart"><Bar data={data} options={options} /></div>
    </article>
  )
}

export function StreamsChart({ d }: { d: DashboardData }) {
  const t = useChartTokens()
  const labels = useMemo(() => d.labels.map(dlabel), [d])
  const options = useMemo(() => baseOptions(t, { stacked: true }), [t])
  const cols: Record<string, string> = { SERVPRO: t.s1, Amazon: t.s2, 'Other Resellers': t.s3, 'A/R Collection': t.s4 }
  const names = ['A/R Collection', 'SERVPRO', 'Other Resellers', 'Amazon'].filter((k) => d.streams[k])
  const data = {
    labels,
    datasets: names.map((k) => ({ label: k, data: d.streams[k], backgroundColor: cols[k], stack: 's', borderRadius: 1, barPercentage: 0.78, categoryPercentage: 0.86 })),
  }
  return (
    <section className="card">
      <div className="card-head"><div><h2>Where revenue comes from</h2><p className="sub">Weekly inflows by source.</p></div></div>
      <div className="chart"><Bar data={data} options={options} /></div>
      <div className="legend">{names.map((k) => <span key={k}><i className="box" style={{ background: cols[k] }} />{k}</span>)}</div>
    </section>
  )
}
