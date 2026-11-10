import type { DashboardData } from '@/features/dashboard/types'
import { fullDates, usd } from '@/shared/format'

/** Funding gap: how much extra cash is needed to stay above the buffer, and how many weeks cash is below zero. */
export function FundingGap({ d }: { d: DashboardData }) {
  const buffer = d.floor ?? 0
  const dates = fullDates(d.labels, d.kpis.as_of ?? '')
  const lines: [string, number[]][] = [['rule-date line', d.cash_rules]]
  if (d.ml) lines.push(['ML line', d.ml.cash_ml])
  const stats = lines.map(([name, a]) => {
    const min = Math.min(...a)
    return { name, min, i: a.indexOf(min), need: Math.max(0, buffer - min), below: a.filter((v) => v < 0).length }
  })
  const worst = stats.reduce((a, b) => (b.need > a.need ? b : a))
  const most = stats.reduce((a, b) => (b.below > a.below ? b : a))
  const items: [string, string, string, string][] = [
    [
      'Peak funding need',
      usd(worst.need),
      worst.need > 0 ? 'neg' : 'pos',
      worst.need > 0
        ? `Lowest cash ${usd(worst.min)} in the week ending ${dates[worst.i]} (${worst.name}), against a ${usd(buffer)} buffer.`
        : `No gap: cash stays above the ${usd(buffer)} buffer on every line.`,
    ],
    [
      'Weeks below zero',
      String(most.below),
      most.below > 0 ? 'neg' : 'pos',
      `Weeks with ending cash under $0, out of ${d.cash_rules.length} (${most.name}${stats.length > 1 ? ', the worse of the two' : ''}).`,
    ],
  ]
  return (
    <section className="kpis kpis-2">
      {items.map(([l, v, c, n]) => (
        <div className="kpi" key={l}>
          <div className="kpi-label">{l}</div>
          <div className={`kpi-value ${c}`}>{v}</div>
          <div className="kpi-note">{n}</div>
        </div>
      ))}
    </section>
  )
}
