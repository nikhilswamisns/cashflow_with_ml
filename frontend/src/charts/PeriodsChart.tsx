import { useMemo } from 'react'
import { Bar } from 'react-chartjs-2'
import type { RevenueForecast } from '../data/types'
import { alpha, useChartTokens } from './tokens'
import { baseOptions, MONO } from './base'
import { kfmt } from '../lib/format'

const MON = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
const span = (a: string, b: string) => [`${MON[+a.slice(5) - 1]} ${a.slice(2, 4)}`, `– ${MON[+b.slice(5) - 1]} ${b.slice(2, 4)}`]

// 12-month blocks counted back from the last actual month, then the forecast year as the final block.
export function PeriodsChart({ d }: { d: RevenueForecast }) {
  const t = useChartTokens()
  const blocks = useMemo(() => {
    const h = d.history, out: { label: string[]; value: number; forecast: boolean }[] = []
    for (let end = h.length; end - 12 >= 0; end -= 12) {
      const part = h.slice(end - 12, end)
      out.unshift({ label: span(part[0].date, part[11].date), value: part.reduce((a, x) => a + x.revenue, 0), forecast: false })
    }
    const f = d.forecast
    out.push({ label: span(f[0].date, f[f.length - 1].date), value: f.reduce((a, x) => a + x.forecast, 0), forecast: true })
    return out
  }, [d])
  const data = {
    labels: blocks.map((b) => b.label),
    datasets: [{
      label: 'Revenue', data: blocks.map((b) => b.value), borderRadius: 4,
      backgroundColor: blocks.map((b) => (b.forecast ? alpha(t.ml, 0.55) : t.cash)), borderColor: blocks.map((b) => (b.forecast ? t.ml : 'transparent')), borderWidth: 1.5,
    }],
  }
  const labelPlugin = useMemo(() => ({
    id: 'barLabels',
    afterDatasetsDraw(chart: any) {
      const { ctx } = chart; ctx.save(); ctx.fillStyle = t.text; ctx.font = `500 11.5px ${MONO}`; ctx.textAlign = 'center'
      chart.getDatasetMeta(0).data.forEach((bar: any, i: number) => ctx.fillText(kfmt(blocks[i].value), bar.x, bar.y - 6))
      ctx.restore()
    },
  }), [t, blocks])
  const options = useMemo(() => {
    const o = baseOptions(t) as any
    o.layout.padding.top = 22
    o.scales.x.ticks = { autoSkip: false, color: t.tick, font: { family: MONO, size: 11 }, maxRotation: 0 }
    o.plugins.tooltip.callbacks.label = (c: any) => ` ${blocks[c.dataIndex].forecast ? 'Forecast' : 'Actual'}: ${kfmt(c.parsed.y)}`
    return o
  }, [t, blocks])
  return <Bar data={data} options={options} plugins={[labelPlugin]} />
}
