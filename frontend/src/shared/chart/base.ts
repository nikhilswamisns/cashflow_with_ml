import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  BarElement,
  LineElement,
  PointElement,
  Filler,
  Tooltip,
  type ChartOptions,
  type Scale,
  type TooltipItem,
} from 'chart.js'
import { tickMoney, usd } from '@/shared/format'
import type { Tokens } from '@/shared/chart/tokens'
ChartJS.register(CategoryScale, LinearScale, BarElement, LineElement, PointElement, Filler, Tooltip)

export const MONO = '"Geist Mono Variable", ui-monospace, monospace'
export const SANS = '"Geist Variable", system-ui, sans-serif'

// Show every Nth week label depending on chart width; all 52 points stay in the data.
function weekTicks(t: Tokens) {
  return {
    color: t.tick,
    font: { family: MONO, size: 11 },
    autoSkip: false,
    maxRotation: 0,
    minRotation: 0,
    callback(this: Scale, value: string | number, index: number) {
      const count = this.chart.data.labels?.length ?? 0,
        w = this.chart.width
      const step =
        count <= 14
          ? w > 640
            ? 1
            : 2
          : count <= 27
            ? w > 700
              ? 2
              : 4
            : w > 1000
              ? 4
              : w > 560
                ? 6
                : w > 460
                  ? 9
                  : 13
      return index % step === 0 ? this.getLabelForValue(Number(value)) : ''
    },
  }
}

/** Options shared by every line and bar chart; assignable to both. */
export type CartesianOptions = ChartOptions<'line'> & ChartOptions<'bar'>

export function baseOptions(t: Tokens, opts: { stacked?: boolean; yTicks?: number } = {}): CartesianOptions {
  return {
    responsive: true,
    maintainAspectRatio: false,
    animation: { duration: 350 },
    interaction: { mode: 'index', intersect: false },
    layout: { padding: { top: 6, right: 6 } },
    plugins: {
      legend: { display: false },
      tooltip: {
        backgroundColor: t.surface,
        titleColor: t.text,
        bodyColor: t.text2,
        borderColor: t.borderStrong,
        borderWidth: 1,
        padding: 10,
        cornerRadius: 8,
        boxPadding: 4,
        titleFont: { family: SANS, weight: 600 },
        bodyFont: { family: MONO, size: 12 },
        filter: (i: TooltipItem<'line' | 'bar'>) => !i.dataset.hideTip,
        callbacks: { label: (c: TooltipItem<'line' | 'bar'>) => ` ${c.dataset.label}: ${usd(c.parsed.y ?? 0)}` },
      },
    },
    scales: {
      x: { stacked: opts.stacked, grid: { display: false }, border: { color: t.border }, ticks: weekTicks(t) },
      y: {
        stacked: opts.stacked,
        grid: { color: t.grid },
        border: { display: false },
        grace: '4%',
        ticks: {
          color: t.tick,
          font: { family: MONO, size: 11 },
          maxTicksLimit: opts.yTicks ?? 6,
          callback: (v: string | number) => tickMoney(+v),
        },
      },
    },
  }
}
