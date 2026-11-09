import { useEffect, useState } from 'react'
import * as Dialog from '@radix-ui/react-dialog'
import { useQueryClient } from '@tanstack/react-query'
import { X } from 'lucide-react'
import { fetchOpeningCash, saveOpeningCash } from '../data/source'
import type { OpeningCash } from '../data/types'
import { usd } from '../lib/format'
import { useToast } from '../lib/toast'

const money = (n: number) => (n < 0 ? '−' : '') + '$' + Math.abs(n).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
const today = () => { const d = new Date(); return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}` }

export function OpeningCashDialog({ runId, open, onOpenChange }: { runId: string; open: boolean; onOpenChange: (o: boolean) => void }) {
  const qc = useQueryClient()
  const toast = useToast()
  const [oc, setOc] = useState<OpeningCash | null>(null)
  const [err, setErr] = useState('')
  const [amount, setAmount] = useState('')
  const [asOf, setAsOf] = useState('')
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    if (!open || !runId) return
    setOc(null); setErr('')
    fetchOpeningCash(runId).then((j) => {
      setOc(j); setAmount(j.override !== null ? String(j.override) : ''); setAsOf((j.override_as_of || j.run_date || '').slice(0, 10))
    }).catch((e: Error) => setErr(e.message))
  }, [open, runId])

  async function save(amt: number, date: string, done: string) {
    setBusy(true)
    try {
      await saveOpeningCash(runId, amt, date)
      await qc.invalidateQueries()   // every figure for this run can change
      toast(done, 'ok'); onOpenChange(false)
    } catch (e) { toast('Opening cash: ' + (e as Error).message, 'error') }
    finally { setBusy(false) }
  }
  const apply = () => {
    const amt = parseFloat(amount)
    if (isNaN(amt) || !asOf) { toast('Enter the bank balance and its date.', 'error'); return }
    void save(amt, asOf, `Opening cash set to ${usd(amt)} for this run.`)
  }

  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay className="dlg-overlay" />
        <Dialog.Content className="dlg" aria-describedby={undefined}>
          <div className="dlg-head">
            <Dialog.Title>Opening cash</Dialog.Title>
            <Dialog.Close className="icon-btn" aria-label="Close"><X size={18} /></Dialog.Close>
          </div>
          {err && <p className="insight warn">{err}</p>}
          {!oc && !err && <p className="sub">Loading…</p>}
          {oc && (
            <>
              <p className="sub">Forecast {oc.run_date} · sum of the Zoho bank accounts at the last sync, not live.</p>
              <table className="oc-table">
                <tbody>
                  {oc.accounts.map((a) => <tr key={a.name}><td>{a.name}</td><td className="num">{money(a.balance)}</td></tr>)}
                  <tr className="sub"><td>Zoho cash</td><td className="num">{money(oc.zoho_cash)}</td></tr>
                  {(oc.manual_adjustments || []).map((a) => <tr key={a.label}><td>{a.label}</td><td className="num">{money(a.amount)}</td></tr>)}
                  <tr className="tot"><td>Opening cash in this forecast{oc.override !== null ? ' (bank override)' : ''}</td><td className="num">{money(oc.opening_cash)}</td></tr>
                </tbody>
              </table>
              <div className="oc-form">
                <label>Bank balance<input inputMode="decimal" value={amount} onChange={(e) => setAmount(e.target.value)} placeholder="e.g. 59834.04" /></label>
                <label>As of<input type="date" value={asOf} onChange={(e) => setAsOf(e.target.value)} /></label>
              </div>
              <div className="dlg-actions">
                <button className="btn ghost" disabled={busy || oc.override === null} onClick={() => void save(0, asOf || today(), 'Opening cash back to Zoho cash + logged adjustments.')}>Back to Zoho cash</button>
                <button className="btn primary" disabled={busy} onClick={apply}>Apply to this run</button>
              </div>
            </>
          )}
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  )
}
