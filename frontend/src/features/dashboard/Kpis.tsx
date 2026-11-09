import type { DashboardData } from '@/features/dashboard/types'
import { dlabel, usd } from '@/shared/format'
export function Kpis({ d }: { d: DashboardData }) {
  const k = d.kpis
  const negWeeks = d.cash_rules.filter((v) => v < 0).length
  const minI = d.cash_rules.indexOf(Math.min(...d.cash_rules))
  const items: [string, string, string, string][] = [
    ['Opening cash', usd(k.opening_cash), '', 'Bank balance in Zoho at the last sync.'],
    [
      'Lowest cash ahead',
      usd(k.lowest_cash),
      k.lowest_cash < 0 ? 'neg' : '',
      `Week ending ${dlabel(d.labels[minI])}. Below zero for ${negWeeks} weeks.`,
    ],
    [
      'Cash after 52 weeks',
      usd(k.ending_cash),
      'pos',
      `${k.net_change >= 0 ? 'Up' : 'Down'} ${usd(Math.abs(k.net_change))} on today.`,
    ],
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
