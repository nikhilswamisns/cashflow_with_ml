import { useState } from 'react'
import * as Dialog from '@radix-ui/react-dialog'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { X } from 'lucide-react'
import { fetchOpeningCash, saveOpeningCash } from '@/features/sync/api'
import type { OpeningCash } from '@/features/sync/types'
import { usd } from '@/shared/format'
import { useToast } from '@/shared/toast'

const money = (n: number) =>
  (n < 0 ? '−' : '') + '$' + Math.abs(n).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
const today = () => {
  const d = new Date()
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}

export function OpeningCashDialog({
  runId,
  open,
  onOpenChange,
}: {
  runId: string
  open: boolean
  onOpenChange: (o: boolean) => void
}) {
  // fetched fresh each time the dialog opens; gcTime 0 drops the copy when it closes
  const { data: oc, error } = useQuery({
    queryKey: ['opening-cash', runId],
    queryFn: () => fetchOpeningCash(runId),
    enabled: open && !!runId,
    gcTime: 0,
  })
  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay className="dlg-overlay" />
        <Dialog.Content className="dlg" aria-describedby={undefined}>
          <div className="dlg-head">
            <Dialog.Title>Opening cash</Dialog.Title>
            <Dialog.Close className="icon-btn" aria-label="Close">
              <X size={18} />
            </Dialog.Close>
          </div>
          {error && <p className="insight warn">{error.message}</p>}
          {!oc && !error && <p className="sub">Loading…</p>}
          {oc && <OpeningCashForm runId={runId} oc={oc} onDone={() => onOpenChange(false)} />}
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  )
}

/** Mounted only once the data is in, so the fields start from it without any effect. */
function OpeningCashForm({ runId, oc, onDone }: { runId: string; oc: OpeningCash; onDone: () => void }) {
  const qc = useQueryClient()
  const toast = useToast()
  const [amount, setAmount] = useState(oc.override !== null ? String(oc.override) : '')
  const [asOf, setAsOf] = useState((oc.override_as_of || oc.run_date || '').slice(0, 10))
  const [busy, setBusy] = useState(false)

  async function save(amt: number, date: string, done: string) {
    setBusy(true)
    try {
      await saveOpeningCash(runId, amt, date)
      await qc.invalidateQueries() // every figure for this run can change
      toast(done, 'ok')
      onDone()
    } catch (e) {
      toast('Opening cash: ' + (e as Error).message, 'error')
    } finally {
      setBusy(false)
    }
  }
  const apply = () => {
    const amt = parseFloat(amount)
    if (isNaN(amt) || !asOf) {
      toast('Enter the bank balance and its date.', 'error')
      return
    }
    void save(amt, asOf, `Opening cash set to ${usd(amt)} for this run.`)
  }

  return (
    <>
      <p className="sub">Forecast {oc.run_date} · sum of the Zoho bank accounts at the last sync, not live.</p>
      <table className="oc-table">
        <tbody>
          {oc.accounts.map((a) => (
            <tr key={a.name}>
              <td>{a.name}</td>
              <td className="num">{money(a.balance)}</td>
            </tr>
          ))}
          <tr className="sub">
            <td>Zoho cash</td>
            <td className="num">{money(oc.zoho_cash)}</td>
          </tr>
          {(oc.manual_adjustments || []).map((a) => (
            <tr key={a.label}>
              <td>{a.label}</td>
              <td className="num">{money(a.amount)}</td>
            </tr>
          ))}
          <tr className="tot">
            <td>Opening cash in this forecast{oc.override !== null ? ' (bank override)' : ''}</td>
            <td className="num">{money(oc.opening_cash)}</td>
          </tr>
        </tbody>
      </table>
      <div className="oc-form">
        <label>
          Bank balance
          <input
            inputMode="decimal"
            value={amount}
            onChange={(e) => setAmount(e.target.value)}
            placeholder="e.g. 59834.04"
          />
        </label>
        <label>
          As of
          <input type="date" value={asOf} onChange={(e) => setAsOf(e.target.value)} />
        </label>
      </div>
      <div className="dlg-actions">
        <button
          className="btn ghost"
          disabled={busy || oc.override === null}
          onClick={() => void save(0, asOf || today(), 'Opening cash back to Zoho cash + logged adjustments.')}
        >
          Back to Zoho cash
        </button>
        <button className="btn primary" disabled={busy} onClick={apply}>
          Apply to this run
        </button>
      </div>
    </>
  )
}
