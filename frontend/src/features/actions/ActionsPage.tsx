import { useActions } from '@/features/actions/hooks'
import { PageLoading } from '@/shared/ui/Loading'
import type { ActionItem } from '@/features/actions/types'
import { useRun } from '@/features/runs/RunProvider'
import { dlabel, usd } from '@/shared/format'

const day = (iso: string) => dlabel(iso.slice(5))
const plural = (n: number, w: string) => `${n} ${w}${n === 1 ? '' : 's'}`

function Table({ rows, kind, hidden }: { rows: ActionItem[]; kind: 'invoice' | 'bill'; hidden: number }) {
  return (
    <div className="act-table-wrap">
      <table className="act-table">
        <thead>
          <tr>
            <th>{kind === 'invoice' ? 'Customer' : 'Vendor'}</th>
            <th className="ref">{kind === 'invoice' ? 'Invoice' : 'Bill'}</th>
            <th>Due</th>
            <th>{kind === 'invoice' ? 'Days overdue' : 'Status'}</th>
            <th>Amount</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={`${r.number}-${i}`}>
              <td className="party" title={r.party ?? ''}>
                {r.party || '–'}
              </td>
              <td className="ref" title={r.number ?? ''}>
                {r.number || '–'}
              </td>
              <td>{day(r.due_date)}</td>
              <td className={r.days_overdue > 0 ? 'late' : ''}>
                {r.days_overdue > 0
                  ? `${plural(r.days_overdue, 'day')} late`
                  : `in ${plural(r.days_until_due ?? 0, 'day')}`}
              </td>
              <td className="num">{usd(r.amount)}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {hidden > 0 && <p className="fine">+ {hidden} more</p>}
    </div>
  )
}

/** What to chase and what to pay now: overdue invoices (biggest amount x days late first) and bills due soon. */
export function ActionsPage() {
  const { runId } = useRun()
  const { data: a, isPending, error } = useActions(runId)
  if (isPending && runId)
    return <PageLoading />
  if (!a)
    return (
      <main className="page">
        <div className="card placeholder">
          <h2>No actions for this run</h2>
          <p>{error?.message ?? 'This run has no open invoices and bills stored with it.'}</p>
        </div>
      </main>
    )
  const { invoices: inv, bills } = a
  const tiles: [string, string, string, string][] = [
    ['Overdue invoices', usd(inv.total), inv.count ? 'neg' : 'pos', `${plural(inv.count, 'invoice')} to chase`],
    ['Bills due soon', usd(bills.total), '', `${plural(bills.count, 'bill')} due within ${a.window_days} days`],
    [
      'Bills already late',
      usd(bills.overdue_total),
      bills.overdue_count ? 'neg' : 'pos',
      bills.overdue_count ? `${plural(bills.overdue_count, 'bill')} past the due date` : 'None past the due date',
    ],
  ]
  return (
    <main className="page">
      <section className="kpis kpis3">
        {tiles.map(([l, v, c, n]) => (
          <div className="kpi" key={l}>
            <div className="kpi-label">{l}</div>
            <div className={`kpi-value ${c}`}>{v}</div>
            <div className="kpi-note">{n}</div>
          </div>
        ))}
      </section>
      <p className="fine">
        As of {day(a.as_of)}, when Zoho was last read. Invoices are ranked by amount × days overdue. Bills are those due
        within {a.window_days} days: late ones first, then the soonest due.
      </p>
      <section className="grid2 act-grid">
        <article className="card">
          <div className="card-head tight">
            <div>
              <h2>Chase these invoices</h2>
              <p className="sub">Overdue, biggest first.</p>
            </div>
          </div>
          {inv.count === 0 ? (
            <p className="insight">No overdue invoices.</p>
          ) : (
            <Table rows={inv.items} kind="invoice" hidden={inv.count - inv.items.length} />
          )}
        </article>
        <article className="card">
          <div className="card-head tight">
            <div>
              <h2>Pay or plan these bills</h2>
              <p className="sub">Late first, then soonest due.</p>
            </div>
          </div>
          {bills.count === 0 ? (
            <p className="insight">No bills due in the next {a.window_days} days.</p>
          ) : (
            <Table rows={bills.items} kind="bill" hidden={bills.count - bills.items.length} />
          )}
        </article>
      </section>
    </main>
  )
}
