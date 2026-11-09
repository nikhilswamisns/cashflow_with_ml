import { useMemo } from 'react'
import { Line } from 'react-chartjs-2'
import type { Chart, ChartData, ChartOptions, Plugin, TooltipItem } from 'chart.js'
import type { RevenueForecast } from '@/features/revenue/types'
import { alpha, useChartTokens } from '@/shared/chart/tokens'
import { baseOptions, MONO } from '@/shared/chart/base'
import { tickMoney, usd } from '@/shared/format'
import type { Tokens } from '@/shared/chart/tokens'
// thin dashed line where the actuals end and the forecast begins
const startMarker = (t: Tokens, at: number): Plugin<'line'> => ({
  id: 'fcStart',
  afterDatasetsDraw(chart: Chart<'line'>) {
    const x = chart.scales.x.getPixelForValue(at),
      { top, bottom } = chart.chartArea,
      ctx = chart.ctx
    ctx.save()
    ctx.strokeStyle = t.borderStrong
    ctx.setLineDash([4, 4])
    ctx.beginPath()
    ctx.moveTo(x, top)
    ctx.lineTo(x, bottom)
    ctx.stroke()
    ctx.setLineDash([])
    ctx.fillStyle = t.tick
    ctx.font = `500 11px ${MONO}`
    ctx.textAlign = 'left'
    ctx.fillText('Forecast starts', x + 6, top + 12)
    ctx.restore()
  },
})

export function RevenueChart({ d, months }: { d: RevenueForecast; months: number | 'all' }) {
  const t = useChartTokens()
  const hist = useMemo(() => (months === 'all' ? d.history : d.history.slice(-months)), [d, months])
  const nH = hist.length
  const data = useMemo<ChartData<'line'>>(() => {
    const lastV = hist[nH - 1].revenue
    const pad = (arr: number[]) => new Array<number | null>(nH - 1).fill(null).concat(arr)
    return {
      labels: hist.map((h) => h.date).concat(d.forecast.map((f) => f.date)),
      datasets: [
        {
          label: 'Range low',
          data: pad([lastV, ...d.forecast.map((f) => f.low)]),
          borderColor: alpha(t.ml, 0.5),
          borderWidth: 1,
          pointRadius: 0,
          fill: false,
          order: 3,
          hideTip: true,
        },
        {
          label: 'Likely range',
          data: pad([lastV, ...d.forecast.map((f) => f.high)]),
          borderColor: alpha(t.ml, 0.5),
          borderWidth: 1,
          pointRadius: 0,
          fill: '-1',
          backgroundColor: alpha(t.ml, 0.16),
          order: 3,
          hideTip: true,
        },
        {
          label: 'Forecast',
          data: pad([lastV, ...d.forecast.map((f) => f.forecast)]),
          borderColor: t.ml,
          borderWidth: 2.5,
          borderDash: [7, 5],
          pointRadius: 3,
          pointBackgroundColor: t.ml,
          tension: 0.15,
          order: 1,
        },
        {
          label: 'Actual revenue',
          data: hist.map((h) => h.revenue).concat(new Array(d.forecast.length).fill(null)),
          borderColor: t.cash,
          borderWidth: 2.2,
          pointRadius: 0,
          tension: 0.15,
          order: 2,
        },
      ],
    }
  }, [d, hist, nH, t])

  const options = useMemo<ChartOptions<'line'>>(() => {
    const b: ChartOptions<'line'> = baseOptions(t)
    return {
      ...b,
      plugins: {
        ...b.plugins,
        tooltip: {
          ...b.plugins?.tooltip,
          filter: (i: TooltipItem<'line'>) => i.raw != null && !i.dataset.hideTip,
          callbacks: { label: (c: TooltipItem<'line'>) => ` ${c.dataset.label}: ${usd(c.parsed.y ?? 0)}` },
        },
      },
      scales: {
        ...b.scales,
        x: {
          ...b.scales?.x,
          ticks: { color: t.tick, maxTicksLimit: 12, maxRotation: 0, font: { family: MONO, size: 11 } },
        },
        y: {
          ...b.scales?.y,
          beginAtZero: true,
          ticks: { ...b.scales?.y?.ticks, callback: (v: string | number) => tickMoney(Number(v)) },
        },
      },
    }
  }, [t])
  const plugins = useMemo(() => [startMarker(t, nH - 1)], [t, nH])
  return <Line data={data} options={options} plugins={plugins} />
}
