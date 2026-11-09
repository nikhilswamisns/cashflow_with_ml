import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { fetchConfig, saveConfig } from '@/features/config/api'
import type { ConfigTable } from '@/features/config/types'
import { useToast } from '@/shared/toast'

const TABLES: [ConfigTable, string][] = [
  ['assumptions', 'Assumptions & Rules'],
  ['corporate_accounts', 'Corporate Accounts'],
  ['freight_duty_vendors', 'Freight & Duty Vendors'],
  ['cc_category_coa_map', 'Credit Card Category Map'],
]

// Same as /ui2: the raw JSON of the server's config file, edited in place. Nothing is saved until you press the button.
export function AssumptionsPage() {
  const [table, setTable] = useState<ConfigTable>('assumptions')
  // always re-read the file when you open a table: you are about to edit the live value
  const { data, error, isFetching, dataUpdatedAt } = useQuery({
    queryKey: ['config', table],
    queryFn: () => fetchConfig(table),
    staleTime: 0,
    gcTime: 0,
  })

  return (
    <main className="page">
      <section className="card">
        <div className="card-head">
          <div>
            <h2>Engine assumptions and rule tables</h2>
            <p className="sub">View and adjust payroll schedules, recurring rent, loan amortizations and run-rates.</p>
          </div>
          <select
            className="field"
            value={table}
            onChange={(e) => setTable(e.target.value as ConfigTable)}
            aria-label="Table"
          >
            {TABLES.map(([k, l]) => (
              <option key={k} value={k}>
                {l}
              </option>
            ))}
          </select>
        </div>
        {error ? (
          <p className="insight warn">This table could not be loaded: {error.message}</p>
        ) : !data || (isFetching && !dataUpdatedAt) ? (
          <textarea
            className="json-editor"
            value="Loading…"
            disabled
            aria-label="Configuration JSON"
            rows={24}
            readOnly
          />
        ) : (
          <JsonEditor key={`${table}:${dataUpdatedAt}`} table={table} initial={JSON.stringify(data, null, 2)} />
        )}
      </section>
    </main>
  )
}

/** Remounted (via key) whenever a table is loaded, so the text always starts from the server's copy. */
function JsonEditor({ table, initial }: { table: ConfigTable; initial: string }) {
  const toast = useToast()
  const [text, setText] = useState(initial)
  const [saving, setSaving] = useState(false)

  async function save() {
    let body: unknown
    try {
      body = JSON.parse(text)
    } catch (e) {
      toast('Error saving config: ' + (e as Error).message, 'error', 8000)
      return
    }
    setSaving(true)
    try {
      await saveConfig(table, body)
      toast('Configuration saved.', 'ok')
    } catch (e) {
      toast('Error saving config: ' + (e as Error).message, 'error', 8000)
    } finally {
      setSaving(false)
    }
  }

  return (
    <>
      <textarea
        className="json-editor"
        value={text}
        onChange={(e) => setText(e.target.value)}
        spellCheck={false}
        aria-label="Configuration JSON"
        rows={24}
      />
      <div className="config-footer">
        <button className="btn primary" onClick={() => void save()} disabled={saving}>
          {saving ? 'Saving…' : 'Save & Invalidate Cache'}
        </button>
        <span className="fine">Changes take effect immediately on the next run calculation.</span>
      </div>
    </>
  )
}
