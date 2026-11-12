import { Link } from 'react-router-dom'
import type { DashboardData } from '@/features/dashboard/types'
import { KpiCard, type KpiSlide } from '@/features/dashboard/KpiCard'
import { useLoans } from '@/features/loans/hooks'
import { fullDates, usd } from '@/shared/format'

/** Funding gap: how much extra cash is needed to stay above the buffer, and how many weeks cash is below zero. */
export function FundingGap({ d }: { d: DashboardData }) {
  const { data: loans } = useLoans()
  const buffer = d.floor ?? 0
  const dates = fullDates(d.labels, d.kpis.as_of ?? '')
  const lines: [string, number[]][] = [['our assumptions', d.cash_rules]]
  if (d.ml) lines.push(['AI model', d.ml.cash_ml])
  const stats = lines.map(([name, a]) => {
    const min = Math.min(...a)
    return { name, min, i: a.indexOf(min), need: Math.max(0, buffer - min), below: a.filter((v) => v < 0).length }
  })
  const tag = (n: string) => (stats.length > 1 ? '' : ` (${n})`) // with two views the card's own label says which one is showing
  const view = (n: string) => (n === 'AI model' ? 'AI model' : 'Our assumptions')
  const needSlides: KpiSlide[] = stats.map((s) => ({
    view: view(s.name),
    value: usd(s.need),
    tone: s.need > 0 ? 'neg' : 'pos',
    note:
      s.need > 0
        ? `Lowest cash ${usd(s.min)} in the week ending ${dates[s.i]}${tag(s.name)}, against a ${usd(buffer)} buffer.`
        : `No gap: cash stays above the ${usd(buffer)} buffer${tag(s.name)}.`,
  }))
  const belowSlides: KpiSlide[] = stats.map((s) => ({
    view: view(s.name),
    value: String(s.below),
    tone: s.below > 0 ? 'neg' : 'pos',
    note: `Weeks with ending cash under $0, out of ${d.cash_rules.length}${tag(s.name)}.`,
  }))
  return (
    <section className={`kpis ${loans ? 'kpis3' : 'kpis-2'}`}>
      <KpiCard label="Peak funding need" slides={needSlides} />
      <KpiCard label="Weeks below zero" slides={belowSlides} />
      {loans && (
        <div className="kpi">
          <div className="kpi-label">Credit headroom</div>
          <div className={`kpi-value ${loans.credit_lines && loans.headroom < 0 ? 'neg' : ''}`}>
            {loans.credit_lines ? usd(loans.headroom) : '–'}
          </div>
          <div className="kpi-note">
            {loans.credit_lines ? (
              `${usd(loans.drawn)} drawn of ${usd(loans.limit)} across ${loans.credit_lines} credit ${loans.credit_lines === 1 ? 'line' : 'lines'}.`
            ) : (
              <>
                No credit lines entered yet.{' '}
                <Link to={{ pathname: '/assumptions', search: '?table=loans' }}>Add them</Link>.
              </>
            )}
          </div>
        </div>
      )}
    </section>
  )
}
