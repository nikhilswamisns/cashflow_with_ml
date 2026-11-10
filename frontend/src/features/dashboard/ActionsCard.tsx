import { useActions } from '@/features/dashboard/hooks'
import { useRun } from '@/features/runs/RunProvider'
import type { ActionItem } from '@/features/dashboard/types'
import { dlabel, usd } from '@/shared/format'

const day = (iso: string) => dlabel(iso.slice(5))

function Table({
  rows,
  last,
  count,
  kind,
}: {
  rows: ActionItem[]
  last: string
  count: number
  kind: 'invoice' | 'bill'
}) {
  return (
    <div className="act-table-wrap">
      <table className="act-table">
        <thead>
          <tr>
            <th>{kind === 'invoice' ? 'Customer' : 'Vendor'}</th>
            <th>{kind === 'invoice' ? 'Invoice' : 'Bill'}</th>
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
              <td>{r.number || '–'}</td>
              <td>{day(r.due_date)}</td>
              <td className={r.days_overdue > 0 ? 'late' : ''}>
                {r.days_overdue > 0
                  ? `${r.days_overdue} ${r.days_overdue === 1 ? 'day' : 'days'} late`
                  : `in ${r.days_until_due} ${r.days_until_due === 1 ? 'day' : 'days'}`}
              </td>
              <td className="num">{usd(r.amount)}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {count > rows.length && <p className="fine">{last}</p>}
    </div>
  )
}

/** What to chase and what to pay now: overdue invoices (biggest amount x days late first) and bills due soon. */
export function ActionsCard() {
  const { runId } = useRun()
  const { data: a } = useActions(runId)
  if (!a) return null // loading, or an older run that has no open items stored
  const { invoices: inv, bills } = a
  return (
    <section className="card">
      <div className="card-head">
        <div>
          <h2>This week's actions</h2>
          <p className="sub">
            As of {day(a.as_of)}, when Zoho was last read. Invoices are ranked by amount × days overdue; bills are those
            due within {a.window_days} days.
          </p>
        </div>
      </div>
      <div className="grid2">
        <div>
          <h3 className="act-head">
            Chase these invoices
            <span>
              {inv.count} overdue · {usd(inv.total)}
            </span>
          </h3>
          {inv.count === 0 ? (
            <p className="insight">No overdue invoices.</p>
          ) : (
            <Table
              rows={inv.items}
              count={inv.count}
              kind="invoice"
              last={`+ ${inv.count - inv.items.length} more overdue`}
            />
          )}
        </div>
        <div>
          <h3 className="act-head">
            Pay or plan these bills
            <span>
              {bills.count} due · {usd(bills.total)}
              {bills.overdue_count > 0 ? ` · ${bills.overdue_count} already late (${usd(bills.overdue_total)})` : ''}
            </span>
          </h3>
          {bills.count === 0 ? (
            <p className="insight">No bills due in the next {a.window_days} days.</p>
          ) : (
            <Table
              rows={bills.items}
              count={bills.count}
              kind="bill"
              last={`+ ${bills.count - bills.items.length} more bills`}
            />
          )}
        </div>
      </div>
    </section>
  )
}
