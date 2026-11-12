import { useWorkingCapital } from '@/features/workingcapital/hooks'
import { PageLoading } from '@/shared/ui/Loading'
import type { Aging, Shares } from '@/features/workingcapital/types'
import { useRun } from '@/features/runs/RunProvider'
import { dlabel, usd } from '@/shared/format'
import { AgingChart, ShareChart } from '@/features/workingcapital/WcCharts'

const pct = (x: number) => `${Math.round(x * 100)}%`
const days = (n: number | null, missing: string) => (n === null ? missing : `${Math.round(n)} days`)
const plural = (n: number, w: string) => `${n} ${w}${n === 1 ? '' : 's'}`

const CHART_MIN_LATE = 0.02 // chart the late buckets only when at least 2% of the open total is late

/** Summary line plus a chart of the late buckets when there is enough late money to see (details are in the tooltip). */
function AgingBars({ a }: { a: Aging }) {
  const notDue = a.buckets.find((b) => b.label === 'Not due')
  const late = a.total - (notDue?.amount ?? 0)
  const chart = a.total > 0 && late / a.total >= CHART_MIN_LATE
  return (
    <>
      <p className="wc-summary">
        {chart
          ? `${pct(1 - late / a.total)} is not due yet (${usd(notDue?.amount ?? 0)}). Late: ${usd(late)}, by days past due.`
          : a.total === 0
            ? 'Nothing open.'
            : late < 0.5
              ? `Nothing is late: all ${usd(a.total)} is not due yet.`
              : `Almost nothing is late: ${usd(late)} of ${usd(a.total)}, the rest is not due yet.`}
      </p>
      {chart && <AgingChart a={a} />}
    </>
  )
}

function ShareCard({ title, sub, s }: { title: string; sub: string; s: Shares }) {
  return (
    <article className="card">
      <div className="card-head tight">
        <div>
          <h2>{title}</h2>
          <p className="sub">{sub}</p>
        </div>
      </div>
      <ShareChart s={s} />
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
    return <PageLoading />
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
  const noZoho = w.flows_available ? '' : 'Needs Zoho connection'
  const tiles: [string, string, string][] = [
    ['DSO', days(w.dso, noZoho), 'Days to collect: A/R ÷ last 90 days sales × 90'],
    ['DPO', days(w.dpo, noZoho ? noZoho : 'No COGS in Zoho P&L'), 'Days to pay: A/P ÷ last 90 days COGS × 90'],
    ['Open A/R', usd(w.ar.total), `${plural(w.ar.count, 'invoice')}, ${usd(lateAr)} late`],
    ['Open A/P', usd(w.ap.total), `${plural(w.ap.count, 'bill')}, ${usd(lateAp)} late`],
  ]
  return (
    <main className="page">
      <section className="kpis">
        {tiles.map(([l, v, n]) => (
          <div className="kpi" key={l}>
            <div className="kpi-label">{l}</div>
            <div className={`kpi-value ${/\d/.test(v) ? '' : 'wc-text'}`}>{v}</div>
            <div className="kpi-note">{n}</div>
          </div>
        ))}
      </section>
      <p className="fine">
        Open items as of {dlabel(w.as_of.slice(5))}, when Zoho was last read. Late means days past the due date.
        {w.flows_snapshot &&
          (w.flows_snapshot.sample
            ? ' DSO, DPO and sales concentration use SAMPLE figures (a stand-in snapshot, not live Zoho data).'
            : ` DSO, DPO and sales concentration use the last Zoho read, saved ${w.flows_snapshot.saved_at}, because Zoho could not be read now.`)}
        {!w.flows_available &&
          ' DSO, DPO and the sales concentration need a live Zoho connection to read the last 90 days of sales and COGS.'}
        {w.flows_available &&
          w.cogs_90 === null &&
          ' DPO is not shown because the Zoho P&L has no Cost of Goods Sold section.'}
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
        {w.concentration.ar && (
          <ShareCard
            title="Customer concentration: open A/R"
            sub="Share of what is owed to us."
            s={w.concentration.ar}
          />
        )}
        {w.concentration.sales && (
          <ShareCard
            title="Customer concentration: sales"
            sub={`Share of invoices dated in the last ${w.window_days} days.`}
            s={w.concentration.sales}
          />
        )}
      </section>
    </main>
  )
}
