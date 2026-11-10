import type { Chart, Plugin } from 'chart.js'
import type { DashboardData } from '@/features/dashboard/types'
import { alpha, type Tokens } from '@/shared/chart/tokens'
import { SANS } from '@/shared/chart/base'

/** First week from which the rules and ML lines are identical with a zero-width band: no document is left to time, so the rest is a flat run-rate assumption. */
export function assumptionStart(d: DashboardData): number | null {
  const m = d.ml
  if (!m) return null
  let i = d.cash_rules.length
  while (i > 0 && Math.abs(m.cash_ml[i - 1] - d.cash_rules[i - 1]) < 0.5 && Math.abs(m.p90[i - 1] - m.p10[i - 1]) < 0.5)
    i--
  return i > 0 && i < d.cash_rules.length ? i : null
}

// grey band over the assumption weeks, drawn behind the lines
export const assumptionPlugin = (t: Tokens, from: number | null): Plugin<'line'> => ({
  id: 'assumptionZone',
  beforeDatasetsDraw(chart: Chart<'line'>) {
    const count = chart.data.labels?.length ?? 0
    if (from == null || from >= count) return
    const { ctx, chartArea, scales } = chart
    const half = count > 1 ? (scales.x.getPixelForValue(1) - scales.x.getPixelForValue(0)) / 2 : 0
    const x = Math.max(chartArea.left, scales.x.getPixelForValue(from) - half)
    ctx.save()
    ctx.fillStyle = alpha(t.tick, 0.16)
    ctx.fillRect(x, chartArea.top, chartArea.right - x, chartArea.bottom - chartArea.top)
    ctx.font = `500 11px ${SANS}`
    ctx.fillStyle = t.text2
    ctx.textAlign = 'right'
    ctx.textBaseline = 'top'
    ctx.fillText('ASSUMPTION · flat run-rate, not a forecast', chartArea.right - 8, chartArea.top + 6)
    ctx.restore()
  },
})
