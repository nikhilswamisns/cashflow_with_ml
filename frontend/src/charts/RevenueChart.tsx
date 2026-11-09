import { useMemo } from 'react'
import { Line } from 'react-chartjs-2'
import type { RevenueForecast } from '../data/types'
import { alpha, useChartTokens } from './tokens'
import { baseOptions, MONO } from './base'
import { tickMoney, usd } from '../lib/format'
import type { Tokens } from './tokens'

// thin dashed line where the actuals end and the forecast begins
const startMarker = (t: Tokens, at: number) => ({
  id: 'fcStart',
  afterDatasetsDraw(chart: any) {
    const x = chart.scales.x.getPixelForValue(at), { top, bottom } = chart.chartArea, ctx = chart.ctx
    ctx.save(); ctx.strokeStyle = t.borderStrong; ctx.setLineDash([4, 4]); ctx.beginPath(); ctx.moveTo(x, top); ctx.lineTo(x, bottom); ctx.stroke()
    ctx.setLineDash([]); ctx.fillStyle = t.tick; ctx.font = `500 11px ${MONO}`; ctx.textAlign = 'left'; ctx.fillText('Forecast starts', x + 6, top + 12); ctx.restore()
  },
})

export function RevenueChart({ d, months }: { d: RevenueForecast; months: number | 'all' }) {
  const t = useChartTokens()
  const hist = months === 'all' ? d.history : d.history.slice(-months)
  const nH = hist.length
  const lastV = hist[nH - 1].revenue
  const pad = (arr: number[]) => new Array(nH - 1).fill(null).concat(arr)
  const labels = hist.map((h) => h.date).concat(d.forecast.map((f) => f.date))
  const data = useMemo(() => ({
    labels,
    datasets: [
      { label: 'Range low', data: pad([lastV, ...d.forecast.map((f) => f.low)]), borderColor: alpha(t.ml, 0.5), borderWidth: 1, pointRadius: 0, fill: false, order: 3, hideTip: true },
      { label: 'Likely range', data: pad([lastV, ...d.forecast.map((f) => f.high)]), borderColor: alpha(t.ml, 0.5), borderWidth: 1, pointRadius: 0, fill: '-1', backgroundColor: alpha(t.ml, 0.16), order: 3, hideTip: true },
      { label: 'Forecast', data: pad([lastV, ...d.forecast.map((f) => f.forecast)]), borderColor: t.ml, borderWidth: 2.5, borderDash: [7, 5], pointRadius: 3, pointBackgroundColor: t.ml, tension: 0.15, order: 1 },
      { label: 'Actual revenue', data: hist.map((h) => h.revenue).concat(new Array(d.forecast.length).fill(null)), borderColor: t.cash, borderWidth: 2.2, pointRadius: 0, tension: 0.15, order: 2 },
    ],
  }), [d, months, t]) // eslint-disable-line react-hooks/exhaustive-deps

  const options = useMemo(() => {
    const o = baseOptions(t) as any
    o.plugins.tooltip.filter = (i: any) => i.raw != null && !i.dataset.hideTip
    o.scales.x.ticks = { color: t.tick, maxTicksLimit: 12, maxRotation: 0, font: { family: MONO, size: 11 } }
    o.scales.y.beginAtZero = true
    o.scales.y.ticks.callback = (v: number) => tickMoney(v)
    o.plugins.tooltip.callbacks.label = (c: any) => ` ${c.dataset.label}: ${usd(c.parsed.y)}`
    return o
  }, [t])
  const plugins = useMemo(() => [startMarker(t, nH - 1)], [t, nH])
  return <Line data={data as any} options={options} plugins={plugins} />
}
