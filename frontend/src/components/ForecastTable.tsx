import type { RevenueForecast } from '../data/types'
import { usd } from '../lib/format'

const MON = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
const ym = (s: string) => { const [y, m] = s.split('-'); return `${MON[+m - 1]} ${y}` }
const yearAgo = (s: string) => { const [y, m] = s.split('-'); return `${+y - 1}-${m}` }

export function ForecastTable({ d }: { d: RevenueForecast }) {
  const actual = new Map(d.history.map((h) => [h.date, h.revenue]))
  const tot = d.forecast.reduce((a, f) => ({ f: a.f + f.forecast, lo: a.lo + f.low, hi: a.hi + f.high }), { f: 0, lo: 0, hi: 0 })
  const lastYear = d.summary.last12
  return (
    <div className="rev-table-wrap">
      <table className="rev-table">
        <thead><tr><th>Month</th><th>Forecast</th><th>Low</th><th>High</th><th>vs last year</th></tr></thead>
        <tbody>
          {d.forecast.map((f) => {
            const prev = actual.get(yearAgo(f.date))
            const pct = prev ? ((f.forecast - prev) / prev) * 100 : null
            return (
              <tr key={f.date}>
                <td>{ym(f.date)}</td><td className="num">{usd(f.forecast)}</td>
                <td className="num muted">{usd(f.low)}</td><td className="num muted">{usd(f.high)}</td>
                <td className={`num ${pct != null && pct < 0 ? 'neg' : ''}`}>{pct == null ? '—' : `${pct > 0 ? '+' : ''}${Math.round(pct)}%`}</td>
              </tr>
            )
          })}
        </tbody>
        <tfoot>
          <tr><td>12 months</td><td className="num">{usd(tot.f)}</td><td className="num muted">{usd(tot.lo)}</td><td className="num muted">{usd(tot.hi)}</td>
            <td className="num">{lastYear ? `${tot.f >= lastYear ? '+' : ''}${Math.round(((tot.f - lastYear) / lastYear) * 100)}%` : '—'}</td></tr>
        </tfoot>
      </table>
    </div>
  )
}
