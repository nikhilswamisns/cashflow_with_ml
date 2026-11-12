import { useMemo } from 'react'
import { Bar, Doughnut } from 'react-chartjs-2'
import { ArcElement, Chart as ChartJS, Tooltip } from 'chart.js'
import { baseOptions, SANS, MONO } from '@/shared/chart/base'
import { useChartTokens } from '@/shared/chart/tokens'
import { usd } from '@/shared/format'
import type { ChartSpec } from '@/features/chat/api'

ChartJS.register(ArcElement, Tooltip)

/** A small chart under a chat answer. The data comes from the tool results on the server, not from the model's text. */
const DRAW = { duration: 1100, easing: 'easeOutQuart' } as const

export function ChatChart({ spec, delay = 0 }: { spec: ChartSpec; delay?: number }) {
  const t = useChartTokens()
  const palette = [t.s4, t.s1, t.s2, t.outC, t.reseller, t.booked, t.s3]
  const total = spec.values.reduce((s, v) => s + v, 0)
  const barOptions = useMemo(() => {
    const o = baseOptions(t, { yTicks: 4 })
    o.animation = { ...DRAW }
    const tip = o.plugins?.tooltip
    if (tip) tip.callbacks = { label: (c) => ` ${usd(c.parsed.y ?? 0)}` }
    return o
  }, [t])

  const groupedOptions = useMemo(() => {
    const o = baseOptions(t, { yTicks: 4 })
    o.animation = { ...DRAW }
    const tip = o.plugins?.tooltip
    if (tip) tip.callbacks = { label: (c) => ` ${c.dataset.label}: ${usd(c.parsed.y ?? 0)}` }
    return o
  }, [t])

  if (spec.kind === 'doughnut') {
    const data = { labels: spec.labels, datasets: [{ data: spec.values, backgroundColor: spec.labels.map((_, i) => palette[i % palette.length]), borderColor: t.surface, borderWidth: 2 }] }
    return (
      <figure className="chat-chart" style={{ animationDelay: `${delay}s` }}>
        <figcaption>{spec.title}</figcaption>
        <div className="donut">
          <Doughnut
            data={data}
            options={{
              responsive: true,
              maintainAspectRatio: false,
              cutout: '62%',
              animation: { ...DRAW, animateRotate: true, animateScale: true },
              plugins: {
                legend: { display: false },
                tooltip: {
                  backgroundColor: t.surface, titleColor: t.text, bodyColor: t.text2, borderColor: t.borderStrong, borderWidth: 1,
                  titleFont: { family: SANS, weight: 600 }, bodyFont: { family: MONO, size: 12 },
                  callbacks: { label: (c) => ` ${c.label}: ${usd(+c.parsed)} (${total ? Math.round((+c.parsed / total) * 100) : 0}%)` },
                },
              },
            }}
          />
        </div>
        <div className="legend">
          {spec.labels.map((l, i) => (
            <span key={l} title={usd(spec.values[i])}>
              <i className="box" style={{ background: palette[i % palette.length] }} />
              {l} {total ? Math.round((spec.values[i] / total) * 100) : 0}%
            </span>
          ))}
        </div>
      </figure>
    )
  }
  if (spec.values2 && spec.series) {
    const data = {
      labels: spec.labels,
      datasets: [
        { label: spec.series[0], data: spec.values, backgroundColor: t.cash, borderRadius: 3 },
        { label: spec.series[1], data: spec.values2, backgroundColor: t.ml, borderRadius: 3 },
      ],
    }
    return (
      <figure className="chat-chart" style={{ animationDelay: `${delay}s` }}>
        <figcaption>{spec.title}</figcaption>
        <div className="bars">
          <Bar data={data} options={groupedOptions} />
        </div>
        <div className="legend">
          {spec.series.map((n, i) => (
            <span key={n}>
              <i className="box" style={{ background: i ? t.ml : t.cash }} />
              {n}
            </span>
          ))}
        </div>
      </figure>
    )
  }
  const colors = spec.values.map((v, i) =>
    spec.signed ? (v < 0 ? t.outC : t.cash) : spec.labels[i] === 'Not due' ? t.s4 : t.s2,
  )
  const data = { labels: spec.labels, datasets: [{ label: spec.title, data: spec.values, backgroundColor: colors, borderRadius: 3 }] }
  return (
    <figure className="chat-chart" style={{ animationDelay: `${delay}s` }}>
      <figcaption>{spec.title}</figcaption>
      <div className="bars">
        <Bar data={data} options={barOptions} />
      </div>
    </figure>
  )
}
