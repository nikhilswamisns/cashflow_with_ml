import { useEffect, useState } from 'react'
import { fetchConfig, saveConfig } from '../data/source'
import type { ConfigTable } from '../data/types'
import { useToast } from '../lib/toast'

const TABLES: [ConfigTable, string][] = [
  ['assumptions', 'Assumptions & Rules'], ['corporate_accounts', 'Corporate Accounts'],
  ['freight_duty_vendors', 'Freight & Duty Vendors'], ['cc_category_coa_map', 'Credit Card Category Map'],
]

// Same as /ui2: the raw JSON of the server's config file, edited in place. Nothing is saved until you press the button.
export function Assumptions() {
  const toast = useToast()
  const [table, setTable] = useState<ConfigTable>('assumptions')
  const [text, setText] = useState('')
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [loadErr, setLoadErr] = useState('')

  useEffect(() => {
    let live = true
    setLoading(true); setLoadErr('')
    fetchConfig(table).then((d) => { if (live) setText(JSON.stringify(d, null, 2)) })
      .catch((e: Error) => { if (live) { setLoadErr(e.message); toast('Failed to load config: ' + e.message, 'error') } })
      .finally(() => { if (live) setLoading(false) })
    return () => { live = false }
  }, [table, toast])

  async function save() {
    let body: unknown
    try { body = JSON.parse(text) } catch (e) { toast('Error saving config: ' + (e as Error).message, 'error', 8000); return }
    setSaving(true)
    try { await saveConfig(table, body); toast('Configuration saved.', 'ok') }
    catch (e) { toast('Error saving config: ' + (e as Error).message, 'error', 8000) }
    finally { setSaving(false) }
  }

  return (
    <main className="page">
      <section className="card">
        <div className="card-head">
          <div>
            <h2>Engine assumptions and rule tables</h2>
            <p className="sub">View and adjust payroll schedules, recurring rent, loan amortizations and run-rates.</p>
          </div>
          <select className="field" value={table} onChange={(e) => setTable(e.target.value as ConfigTable)} aria-label="Table">
            {TABLES.map(([k, l]) => <option key={k} value={k}>{l}</option>)}
          </select>
        </div>
        {loadErr ? <p className="insight warn">This table could not be loaded: {loadErr}</p> : (
          <textarea className="json-editor" value={loading ? 'Loading…' : text} onChange={(e) => setText(e.target.value)}
            disabled={loading} spellCheck={false} aria-label="Configuration JSON" rows={24} />
        )}
        <div className="config-footer">
          <button className="btn primary" onClick={() => void save()} disabled={loading || saving || !!loadErr}>{saving ? 'Saving…' : 'Save & Invalidate Cache'}</button>
          <span className="fine">Changes take effect immediately on the next run calculation.</span>
        </div>
      </section>
    </main>
  )
}
