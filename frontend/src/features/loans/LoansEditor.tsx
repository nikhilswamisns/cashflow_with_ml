import { useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { Plus, Trash2 } from 'lucide-react'
import { saveLoans } from '@/features/loans/api'
import type { Facility, FacilityType, Loans } from '@/features/loans/types'
import { usd } from '@/shared/format'
import { useToast } from '@/shared/toast'

// numbers stay text while typing so a half-typed value is never rewritten
interface Draft {
  name: string
  type: FacilityType
  limit: string
  drawn: string
  rate: string
  repay: string
}
const n = (s: string) => (s.trim() === '' ? 0 : Number(s))
const blank = (): Draft => ({ name: '', type: 'credit_line', limit: '', drawn: '', rate: '', repay: '' })
const fromSaved = (f: Facility): Draft => ({
  name: f.name,
  type: f.type,
  limit: f.limit ? String(f.limit) : '',
  drawn: f.drawn ? String(f.drawn) : '',
  rate: f.rate_pct ? String(f.rate_pct) : '',
  repay: f.monthly_repayment ? String(f.monthly_repayment) : '',
})
const toFacility = (d: Draft): Facility => ({
  name: d.name.trim(),
  type: d.type,
  limit: n(d.limit),
  drawn: n(d.drawn),
  rate_pct: n(d.rate),
  monthly_repayment: n(d.repay),
})
const interest = (d: Draft) => (n(d.drawn) * n(d.rate)) / 100 / 12

/** Mounted once the saved loans are in (via key), so the rows start from the server's copy. */
export function LoansEditor({ saved }: { saved: Loans }) {
  const toast = useToast()
  const qc = useQueryClient()
  const [rows, setRows] = useState<Draft[]>(saved.facilities.map(fromSaved))
  const [saving, setSaving] = useState(false)
  const set = (i: number, patch: Partial<Draft>) => setRows((r) => r.map((x, k) => (k === i ? { ...x, ...patch } : x)))
  const entered = {
    repay: rows.reduce((a, d) => a + n(d.repay), 0),
    interest: rows.reduce((a, d) => a + interest(d), 0),
  }
  const f = saved.in_forecast

  async function save() {
    if (
      rows.some(
        (d) =>
          Number.isNaN(n(d.limit)) || Number.isNaN(n(d.drawn)) || Number.isNaN(n(d.rate)) || Number.isNaN(n(d.repay)),
      )
    ) {
      toast('Amounts must be numbers.', 'error')
      return
    }
    setSaving(true)
    try {
      await saveLoans(rows.map(toFacility))
      await qc.invalidateQueries({ queryKey: ['loans'] })
      toast('Loans and credit lines saved.', 'ok')
    } catch (e) {
      toast('Could not save: ' + (e as Error).message, 'error', 8000)
    } finally {
      setSaving(false)
    }
  }

  return (
    <>
      <div className="loans-wrap">
        <table className="loans-table">
          <thead>
            <tr>
              <th>Name</th>
              <th>Type</th>
              <th>Limit ($)</th>
              <th>Drawn ($)</th>
              <th>Rate (%/yr)</th>
              <th>Repayment ($/mo)</th>
              <th>Headroom</th>
              <th>Interest ($/mo)</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {rows.map((d, i) => {
              const credit = d.type === 'credit_line'
              const head = n(d.limit) - n(d.drawn)
              return (
                <tr key={i}>
                  <td>
                    <input
                      className="field"
                      aria-label="Name"
                      value={d.name}
                      onChange={(e) => set(i, { name: e.target.value })}
                    />
                  </td>
                  <td>
                    <select
                      className="field"
                      aria-label="Type"
                      value={d.type}
                      onChange={(e) => set(i, { type: e.target.value as FacilityType })}
                    >
                      <option value="credit_line">Credit line</option>
                      <option value="term_loan">Term loan</option>
                    </select>
                  </td>
                  <td>
                    <input
                      className="field num"
                      aria-label="Limit"
                      inputMode="decimal"
                      disabled={!credit}
                      value={credit ? d.limit : ''}
                      onChange={(e) => set(i, { limit: e.target.value })}
                    />
                  </td>
                  <td>
                    <input
                      className="field num"
                      aria-label={credit ? 'Drawn' : 'Outstanding'}
                      inputMode="decimal"
                      placeholder={credit ? '' : 'balance'}
                      value={d.drawn}
                      onChange={(e) => set(i, { drawn: e.target.value })}
                    />
                  </td>
                  <td>
                    <input
                      className="field num"
                      aria-label="Rate"
                      inputMode="decimal"
                      value={d.rate}
                      onChange={(e) => set(i, { rate: e.target.value })}
                    />
                  </td>
                  <td>
                    <input
                      className="field num"
                      aria-label="Repayment"
                      inputMode="decimal"
                      value={d.repay}
                      onChange={(e) => set(i, { repay: e.target.value })}
                    />
                  </td>
                  <td className={`num ${credit && head < 0 ? 'neg' : ''}`}>{credit ? usd(head) : '–'}</td>
                  <td className="num">{usd(interest(d))}</td>
                  <td>
                    <button
                      className="icon-btn"
                      aria-label={`Remove ${d.name || 'row'}`}
                      data-tip="Remove"
                      onClick={() => setRows((r) => r.filter((_, k) => k !== i))}
                    >
                      <Trash2 size={16} />
                    </button>
                  </td>
                </tr>
              )
            })}
            {rows.length === 0 && (
              <tr>
                <td colSpan={9} className="loans-empty">
                  No loans or credit lines entered yet.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
      <div className="config-footer">
        <button className="btn" onClick={() => setRows((r) => [...r, blank()])}>
          <Plus size={16} /> Add a loan or credit line
        </button>
        <button className="btn primary" onClick={() => void save()} disabled={saving}>
          {saving ? 'Saving…' : 'Save'}
        </button>
      </div>
      <div className="loans-compare">
        <div>
          <b>Entered here</b>
          <span>
            Repayments {usd(entered.repay)}/month · interest about {usd(entered.interest)}/month
          </span>
        </div>
        <div>
          <b>Already in the cash forecast</b>
          <span>
            Repayments {usd(f.repayments_per_month)}/month · interest {usd(f.interest_per_month)}/month (fixed lines in
            Assumptions & Rules)
          </span>
        </div>
        <p className="fine">
          This table is for headroom and for checking the forecast. It does not change the forecast, so entering a loan
          here never adds a payment twice.
        </p>
      </div>
    </>
  )
}
