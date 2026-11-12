import type { DashboardData } from '@/features/dashboard/types'
import { KpiCard, type KpiSlide } from '@/features/dashboard/KpiCard'
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
  const lowSlide = (view: string, v: number, i: number, from: string): KpiSlide => ({
    view,
    value: usd(v),
    tone: v < 0 ? 'neg' : '',
    note: from ? `Week ending ${dates[i]} · ${from}` : `Week ending ${dates[i]}`,
  })
  const lowSlides = [lowSlide('Our assumptions', low.v, low.i, d.ml ? '' : line)]
  if (d.ml) {
    const m = minOf(d.ml.cash_ml)
    lowSlides.push(lowSlide('AI model', m.v, m.i, ''))
  }
  const plain: [string, string, string, string][] = [
    [
      'Book cash (Zoho)',
      usd(k.opening_cash),
      '',
      `Zoho book balance${syncedLabel ? ` · ${syncedLabel.replace('Run created ', '').replace(/,.*/, '')}` : ''}`,
    ],
  ]
  const after: [string, string, string, string][] = [
    ['Receivables (A/R)', usd(k.total_ar), '', 'Customers still owe you this.'],
    ['Payables (A/P)', usd(k.total_ap), '', `You owe vendors. A/R covers it ${(k.total_ar / k.total_ap).toFixed(2)}×.`],
  ]
  const card = ([l, v, c, n]: [string, string, string, string]) => (
    <KpiCard key={l} label={l} slides={[{ view: '', value: v, tone: c, note: n }]} />
  )
  return (
    <section className="kpis">
      {plain.map(card)}
      <KpiCard label="Lowest cash ahead" slides={lowSlides} />
      {after.map(card)}
    </section>
  )
}
