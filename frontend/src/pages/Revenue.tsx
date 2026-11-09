import { useState } from 'react'
import { useRevenueForecast } from '../data/hooks'
import { RevenueChart } from '../charts/RevenueChart'
import { alpha, useChartTokens } from '../charts/tokens'

const MON = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
const ym = (s: string) => { const [y, m] = s.split('-'); return `${MON[+m - 1]} ${y}` }
const short = (n: number) => Math.abs(n) >= 1e6 ? `$${(n / 1e6).toFixed(2)}M` : `$${Math.round(n / 1e3)}K`

export function Revenue() {
  const { data: d, error, isPending } = useRevenueForecast()
  const t = useChartTokens()
  const [range, setRange] = useState<24 | 'all'>('all')

  if (error) return <main className="page"><div className="card placeholder"><h2>The revenue forecast could not be loaded</h2><p>{error.message}</p></div></main>
  if (isPending || !d) return <main className="page"><div className="loading">Loading…</div></main>
  const s = d.summary, a = d.accuracy
  const kpis: [string, string, string][] = [
    ['Forecast, next 12 months', short(s.next12), `${ym(d.forecast[0].date)} to ${ym(d.forecast[d.forecast.length - 1].date)}`],
    ['Last 12 months (actual)', short(s.last12), s.growth_pct != null ? `Forecast is ${s.growth_pct > 0 ? '+' : ''}${s.growth_pct}% vs last year` : ''],
    ['Likely range, 12 months', `${short(s.low12)} to ${short(s.high12)}`, 'Wide because growth has been fast'],
  ]
  return (
    <main className="page">
      <section className="kpis kpis3">
        {kpis.map(([l, v, n]) => <div className="kpi" key={l}><div className="kpi-label">{l}</div><div className="kpi-value">{v}</div><div className="kpi-note">{n}</div></div>)}
      </section>
      <section className="card">
        <div className="card-head">
          <div><h2>Monthly revenue: history and next 12 months</h2><p className="sub">{d.model}</p></div>
          <div className="seg" role="group" aria-label="Range">
            {([[24, '2 years'], ['all', 'All']] as const).map(([k, l]) => (
              <button key={k} className={range === k ? 'on' : ''} aria-pressed={range === k} onClick={() => setRange(k)}>{l}</button>
            ))}
          </div>
        </div>
        <div className="chart tall"><RevenueChart d={d} months={range} /></div>
        <div className="legend">
          <span><i style={{ background: t.cash }} />Actual revenue</span>
          <span style={{ color: t.ml }}><i className="dash" /><span style={{ color: 'var(--text-2)' }}>Forecast</span></span>
          <span><i className="box" style={{ background: alpha(t.ml, 0.4) }} />Likely range (4 in 5 months should land inside)</span>
        </div>
        <p className="insight">
          {a ? `In a test on the last 12 months, a single month's forecast missed by about ${Math.round(a.avg_miss_pct)}% on average, and ${a.inside_range} of ${a.months} months landed inside the range. ` : ''}
          Treat the line as the most likely path and the shaded band as the realistic range. Forecasts for later months are less certain than near ones.
        </p>
      </section>
    </main>
  )
}
