import { useState } from 'react'
import * as Dialog from '@radix-ui/react-dialog'
import { X } from 'lucide-react'
import type { LineItem, MatrixCell, MatrixData, MatrixRow } from '@/features/matrix/types'
import { usd } from '@/shared/format'
const dash = '—'
const cellText = (v: number | undefined) => (v === undefined || Math.abs(v) < 0.005 ? dash : usd(v))
const fmtDate = (iso: string) => {
  const [y, m, d] = iso.split('-')
  return `${m}/${d}/${y.slice(2)}`
}

interface Picked {
  label: string
  week: string
  amount: number
  items: LineItem[]
}

export function MatrixTable({ data, weeks, query }: { data: MatrixData; weeks: number; query: string }) {
  const [picked, setPicked] = useState<Picked | null>(null)
  const cols = data.weeks.slice(0, weeks)
  const q = query.trim().toLowerCase()

  const items = (row: MatrixRow, i: number) => {
    const c = row.field ? (data.weeks[i][row.field] as MatrixCell | undefined) : undefined
    return c && typeof c === 'object' && c.line_items?.length ? c : null
  }
  const open = (row: MatrixRow, i: number) => {
    const c = items(row, i)
    if (c)
      setPicked({ label: row.label, week: data.weeks[i].week_ending_friday, amount: c.amount, items: c.line_items! })
  }

  return (
    <>
      <div className="matrix-wrap" tabIndex={0} aria-label="52-week cash flow matrix">
        <table className="matrix">
          <thead>
            <tr>
              <th className="sc c-code">Code</th>
              <th className="sc c-acct">Account</th>
              {cols.map((w) => (
                <th key={w.week_ending_friday} className="c-week">
                  {fmtDate(w.week_ending_friday)}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {data.rows.map((row, ri) => {
              const head = row.kind === 'section' || row.kind === 'group'
              if (q && !head && !`${row.code} ${row.label}`.toLowerCase().includes(q)) return null
              if (head) {
                return (
                  <tr key={ri} className={`r-${row.kind}`}>
                    <td className="sc c-code">{row.code}</td>
                    <td className="sc c-acct">{row.label}</td>
                    <td colSpan={cols.length} />
                  </tr>
                )
              }
              return (
                <tr key={ri} className={`r-${row.kind}`}>
                  <td className="sc c-code">{row.code}</td>
                  <td className="sc c-acct">{row.label}</td>
                  {cols.map((_, i) => {
                    const v = row.values[i]
                    const has = !!items(row, i)
                    const cls = `num${v < -0.005 ? ' neg' : ''}${has ? ' has-items' : ''}`
                    return has ? (
                      <td key={i} className={cls}>
                        <button
                          onClick={() => open(row, i)}
                          aria-label={`${row.label}, week ending ${data.weeks[i].week_ending_friday}: show line items`}
                        >
                          {cellText(v)}
                        </button>
                      </td>
                    ) : (
                      <td key={i} className={cls}>
                        {cellText(v)}
                      </td>
                    )
                  })}
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>

      <Dialog.Root
        open={!!picked}
        onOpenChange={(o) => {
          if (!o) setPicked(null)
        }}
      >
        <Dialog.Portal>
          <Dialog.Overlay className="dlg-overlay" />
          <Dialog.Content className="dlg" aria-describedby={undefined}>
            <div className="dlg-head">
              <Dialog.Title>{picked?.label}</Dialog.Title>
              <Dialog.Close className="icon-btn" aria-label="Close">
                <X size={18} />
              </Dialog.Close>
            </div>
            {picked && (
              <>
                <p className="sub">
                  Week ending {picked.week} · Total: <span className="num">{usd(picked.amount)}</span>
                </p>
                <ul className="li-list">
                  {picked.items.map((li, i) => (
                    <li key={i}>
                      <div>
                        <div className="li-label">{li.label || 'Line item'}</div>
                        <div className="li-ref">{li.raw_ref || 'Direct ledger'}</div>
                      </div>
                      <div className="num li-amt">{usd(li.amount)}</div>
                    </li>
                  ))}
                </ul>
              </>
            )}
          </Dialog.Content>
        </Dialog.Portal>
      </Dialog.Root>
    </>
  )
}
