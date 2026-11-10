import { useTrack } from '@/features/dashboard/hooks'
import { dlabel, usd } from '@/shared/format'

const signed = (n: number) => (n > 0 ? '+' : '') + usd(n)
const day = (iso: string) => `${dlabel(iso.slice(5))}, ${iso.slice(0, 4)}`

/** What each line predicted before the week began, next to what Zoho shows the cash really was. */
export function AccuracyCard() {
  const { data } = useTrack()
  if (!data) return null // loading, or this server cannot read Zoho: the chart simply has no green line either
  const done = data.rows.filter((r) => r.actual != null).reverse()
  const next = data.rows.find((r) => r.actual == null)
  const { weeks_scored: n, avg_miss_rules: mr, avg_miss_ml: mm } = data.summary
  return (
    <section className="card">
      <div className="card-head">
        <div>
          <h2>Forecast vs actual</h2>
          <p className="sub">Ending cash each Friday: what was predicted before the week began, and what happened.</p>
        </div>
      </div>
      {done.length === 0 ? (
        <p className="insight">
          {next
            ? `The first comparison appears after the week ending ${day(next.week_ending)}.`
            : 'No predictions are stored yet.'}
        </p>
      ) : (
        <div className="acc-table-wrap">
          <table className="acc-table">
            <thead>
              <tr>
                <th>Week ending</th>
                <th>Predicted (rules)</th>
                <th>Predicted (ML)</th>
                <th>Actual</th>
                <th>Off by (rules)</th>
                <th>Off by (ML)</th>
                <th>Closer</th>
              </tr>
            </thead>
            <tbody>
              {done.map((r) => (
                <tr key={r.week_ending}>
                  <td>{day(r.week_ending)}</td>
                  <td className="num">{usd(r.rules)}</td>
                  <td className="num">{r.ml == null ? '–' : usd(r.ml)}</td>
                  <td className="num strong">{usd(r.actual as number)}</td>
                  <td className="num">{r.gap_rules == null ? '–' : signed(r.gap_rules)}</td>
                  <td className="num">{r.gap_ml == null ? '–' : signed(r.gap_ml)}</td>
                  <td>{r.closer === 'ml' ? 'ML timing' : r.closer === 'rules' ? 'Rules' : '–'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {n > 0 && mr != null && mm != null && (
        <p className="insight">
          Over <b>{n}</b> completed {n === 1 ? 'week' : 'weeks'}, the rules line missed by <b>{usd(mr)}</b> on average
          and ML timing by <b>{usd(mm)}</b>.
        </p>
      )}
      <p className="fine">
        Predictions are saved when each run is made, for its first {data.horizon_weeks} weeks, and are never changed
        afterwards. Actual is the Zoho book balance today; recent weeks can still move until the books are reconciled.
      </p>
    </section>
  )
}
