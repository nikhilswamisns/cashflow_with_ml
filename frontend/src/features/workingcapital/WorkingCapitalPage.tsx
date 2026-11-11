import { useWorkingCapital } from '@/features/workingcapital/hooks'
import type { Aging, Shares } from '@/features/workingcapital/types'
import { useRun } from '@/features/runs/RunProvider'
import { dlabel, usd } from '@/shared/format'

const pct = (x: number) => `${Math.round(x * 100)}%`
const days = (n: number | null) => (n === null ? 'n/a' : `${Math.round(n)} days`)
const plural = (n: number, w: string) => `${n} ${w}${n === 1 ? '' : 's'}`

/** One horizontal bar per aging bucket, scaled to the biggest bucket. Late buckets are red, "Not due" is neutral. */
function AgingBars({ a }: { a: Aging }) {
  const max = Math.max(...a.buckets.map((b) => b.amount), 1)
  return (
    <div className="wc-bars">
      {a.buckets.map((b) => (
        <div className="wc-row" key={b.label}>
          <span className="wc-label">{b.label === 'Not due' ? b.label : `${b.label} days late`}</span>
          <span className="wc-track">
            <span
              className={`wc-fill ${b.label === 'Not due' ? '' : 'late'}`}
              style={{ width: `${(b.amount / max) * 100}%` }}
            />
          </span>
          <span className="wc-amt">{usd(b.amount)}</span>
          <span className="wc-n">{pct(b.share)}</span>
        </div>
      ))}
    </div>
  )
}

function ShareCard({ title, sub, s }: { title: string; sub: string; s: Shares | null }) {
  if (!s)
    return (
      <article className="card">
        <h2>{title}</h2>
        <p className="insight">Not available: Zoho could not be read for the last 90 days of invoices.</p>
      </article>
    )
  return (
    <article className="card">
      <div className="card-head tight">
        <div>
          <h2>{title}</h2>
          <p className="sub">{sub}</p>
        </div>
      </div>
      <div className="wc-shares">
        <div>
          <div className="kpi-label">{s.focus_name}</div>
          <div className="kpi-value">{pct(s.focus_share)}</div>
        </div>
        <div>
          <div className="kpi-label">Top 5 customers</div>
          <div className="kpi-value">{pct(s.top_share)}</div>
        </div>
      </div>
      <table className="act-table">
        <tbody>
          {s.top.map((t) => (
            <tr key={t.party}>
              <td className="party" title={t.party}>
                {t.party}
              </td>
              <td className="num">{usd(t.amount)}</td>
              <td className="num">{pct(t.share)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </article>
  )
}

/** How fast money comes in and goes out: A/R and A/P aging, DSO, DPO and how concentrated the customers are. */
export function WorkingCapitalPage() {
  const { runId } = useRun()
  const { data: w, isPending, error } = useWorkingCapital(runId)
  if (isPending && runId)
    return (
      <main className="page">
        <div className="loading">Loading…</div>
      </main>
    )
  if (!w)
    return (
      <main className="page">
        <div className="card placeholder">
          <h2>No working capital for this run</h2>
          <p>{error?.message ?? 'This run has no open invoices and bills stored with it.'}</p>
        </div>
      </main>
    )
  const lateAr = w.ar.buckets.filter((b) => b.label !== 'Not due').reduce((t, b) => t + b.amount, 0)
  const lateAp = w.ap.buckets.filter((b) => b.label !== 'Not due').reduce((t, b) => t + b.amount, 0)
  const tiles: [string, string, string][] = [
    ['DSO', days(w.dso), 'Days to collect: A/R ÷ last 90 days sales × 90'],
    ['DPO', days(w.dpo), 'Days to pay: A/P ÷ last 90 days COGS × 90'],
    ['Open A/R', usd(w.ar.total), `${plural(w.ar.count, 'invoice')}, ${usd(lateAr)} late`],
    ['Open A/P', usd(w.ap.total), `${plural(w.ap.count, 'bill')}, ${usd(lateAp)} late`],
  ]
  return (
    <main className="page">
      <section className="kpis">
        {tiles.map(([l, v, n]) => (
          <div className="kpi" key={l}>
            <div className="kpi-label">{l}</div>
            <div className="kpi-value">{v}</div>
            <div className="kpi-note">{n}</div>
          </div>
        ))}
      </section>
      <p className="fine">
        Open items as of {dlabel(w.as_of.slice(5))}, when Zoho was last read. Late means days past the due date.
        {!w.flows_available && ' DSO and DPO are n/a because the last 90 days of sales and COGS could not be read from Zoho.'}
        {w.flows_available && w.cogs_90 === null && ' DPO is n/a because the Zoho P&L has no Cost of Goods Sold section.'}
        {(w.ar.missing_due_date > 0 || w.ap.missing_due_date > 0) &&
          ` ${w.ar.missing_due_date + w.ap.missing_due_date} items have no due date and are counted as not due.`}
      </p>
      <section className="grid2">
        <article className="card">
          <div className="card-head tight">
            <div>
              <h2>Receivables aging</h2>
              <p className="sub">What customers owe, by days past due.</p>
            </div>
          </div>
          <AgingBars a={w.ar} />
        </article>
        <article className="card">
          <div className="card-head tight">
            <div>
              <h2>Payables aging</h2>
              <p className="sub">What we owe vendors, by days past due.</p>
            </div>
          </div>
          <AgingBars a={w.ap} />
        </article>
      </section>
      <section className="grid2">
        <ShareCard title="Customer concentration: open A/R" sub="Share of what is owed to us." s={w.concentration.ar} />
        <ShareCard
          title="Customer concentration: sales"
          sub={`Share of invoices dated in the last ${w.window_days} days.`}
          s={w.concentration.sales}
        />
      </section>
    </main>
  )
}
