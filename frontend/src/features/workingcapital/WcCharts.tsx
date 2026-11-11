import { useMemo } from 'react'
import { Bar } from 'react-chartjs-2'
import type { TooltipItem } from 'chart.js'
import type { Aging, Shares } from '@/features/workingcapital/types'
import { useChartTokens } from '@/shared/chart/tokens'
import { baseOptions } from '@/shared/chart/base'
import { usd } from '@/shared/format'

const pct = (x: number) => `${Math.round(x * 100)}%`

/** Column chart of the late buckets only ("Not due" would dwarf them); red bars, tooltip has amount, items and share of the total. */
export function AgingChart({ a }: { a: Aging }) {
  const late = useMemo(() => a.buckets.filter((b) => b.label !== 'Not due'), [a])
  const t = useChartTokens()
  const options = useMemo(() => {
    const o = baseOptions(t)
    o.interaction = { mode: 'nearest', intersect: true }
    o.plugins!.tooltip!.callbacks = {
      title: (items: TooltipItem<'line' | 'bar'>[]) => `${items[0].label} days late`,
      label: (c: TooltipItem<'line' | 'bar'>) => {
        const b = late[c.dataIndex]
        return ` ${usd(b.amount)} · ${b.count} item${b.count === 1 ? '' : 's'} · ${pct(b.share)}`
      },
    }
    return o
  }, [t, late])
  const data = {
    labels: late.map((b) => b.label),
    datasets: [
      {
        label: 'Open',
        data: late.map((b) => b.amount),
        backgroundColor: t.outC,
        borderRadius: 3,
        barPercentage: 0.7,
        categoryPercentage: 0.8,
      },
    ],
  }
  return (
    <div className="chart wc-chart" role="img" aria-label="Late balance by days past due">
      <Bar data={data} options={options} />
    </div>
  )
}

/** Horizontal bars: each top customer's share of the total, biggest first. */
export function ShareChart({ s }: { s: Shares }) {
  const t = useChartTokens()
  const options = useMemo(() => {
    const o = baseOptions(t)
    o.indexAxis = 'y'
    o.interaction = { mode: 'nearest', intersect: true }
    o.scales = {
      x: {
        min: 0,
        grid: { color: t.grid },
        border: { display: false },
        ticks: { color: t.tick, maxTicksLimit: 5, callback: (v: string | number) => `${Math.round(+v * 100)}%` },
      },
      y: { grid: { display: false }, border: { color: t.border }, ticks: { color: t.tick, font: { size: 11 } } },
    }
    o.plugins!.tooltip!.callbacks = {
      label: (c: TooltipItem<'line' | 'bar'>) =>
        ` ${usd(s.top[c.dataIndex].amount)} · ${pct(s.top[c.dataIndex].share)}`,
    }
    return o
  }, [t, s])
  const data = {
    labels: s.top.map((r) => (r.party.length > 24 ? `${r.party.slice(0, 23)}…` : r.party)),
    datasets: [
      {
        label: 'Share',
        data: s.top.map((r) => r.share),
        backgroundColor: s.top.map((r) =>
          s.focus_name && r.party.toLowerCase().includes(s.focus_name.toLowerCase()) ? t.s1 : t.s3,
        ),
        borderRadius: 3,
        barPercentage: 0.7,
      },
    ],
  }
  return (
    <div className="chart wc-chart" role="img" aria-label="Top customers by share">
      <Bar data={data} options={options} />
    </div>
  )
}
