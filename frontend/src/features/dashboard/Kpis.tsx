import type { DashboardData } from '@/features/dashboard/types'
import { fullDates, usd } from '@/shared/format'

const minOf = (a: number[]) => {
  const v = Math.min(...a)
  return { v, i: a.indexOf(v) }
}

export function Kpis({ d, syncedLabel }: { d: DashboardData; syncedLabel?: string }) {
  const k = d.kpis
  const dates = fullDates(d.labels, k.as_of ?? '')
  const low = minOf(d.cash_rules)
  const line = d.rulesFromSavedRun ? 'saved run' : 'our assumptions'
  const items: [string, string, string, string][] = [
    [
      'Book cash (Zoho)',
      usd(k.opening_cash),
      '',
      `Zoho book balance${syncedLabel ? ` · ${syncedLabel.replace('Run created ', '').replace(/,.*/, '')}` : ''}`,
    ],
    ['Lowest cash ahead', usd(low.v), low.v < 0 ? 'neg' : '', `Week ending ${dates[low.i]} · ${line}`],
    ['Receivables (A/R)', usd(k.total_ar), '', 'Customers still owe you this.'],
    ['Payables (A/P)', usd(k.total_ap), '', `You owe vendors. A/R covers it ${(k.total_ar / k.total_ap).toFixed(2)}×.`],
  ]
  return (
    <section className="kpis">
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
