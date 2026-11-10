import { useRef, useState, type DragEvent } from 'react'
import { CheckCircle2, CircleAlert, FileUp, RefreshCw } from 'lucide-react'
import { autoRun, fetchZohoStatus } from '@/features/sync/api'
import type { ZohoStatus } from '@/features/sync/types'
import { useRun } from '@/features/runs/RunProvider'
import { useSync } from './SyncProvider'
import { useDismissToast, useToast } from '@/shared/toast'
const iso = (d: Date) =>
  `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
function fridayOnOrBefore(d = new Date()) {
  const x = new Date(d)
  x.setDate(x.getDate() - ((x.getDay() + 2) % 7))
  return iso(x)
}

export function DataSyncPage() {
  const { afterRun } = useRun()
  const { sync, syncing } = useSync()
  const toast = useToast()
  const dismiss = useDismissToast()
  const [zoho, setZoho] = useState<ZohoStatus | 'checking' | 'unknown' | null>(null)
  const [syncDate, setSyncDate] = useState(fridayOnOrBefore())
  const [files, setFiles] = useState<File[]>([])
  const [drag, setDrag] = useState(false)
  const [opening, setOpening] = useState('')
  const [asOf, setAsOf] = useState(fridayOnOrBefore())
  const [busy, setBusy] = useState('')
  const fileIn = useRef<HTMLInputElement>(null)

  async function checkZoho() {
    setZoho('checking')
    try {
      setZoho(await fetchZohoStatus())
    } catch {
      setZoho('unknown')
    }
  }

  async function create(label: string, work: () => Promise<{ run_id: string }>, done: string) {
    if (busy) return
    setBusy(label)
    const wait = toast(`${label}…`, 'info', 0)
    try {
      const r = await work()
      await afterRun(r.run_id)
      toast(done, 'ok')
    } catch (e) {
      toast(`${label}: ${(e as Error).message}`, 'error', 8000)
    } finally {
      dismiss(wait)
      setBusy('')
    }
  }

  const pick = (list: FileList | null) => {
    if (!list) return
    const ok = [...list].filter((f) => /\.(xlsx|xls|csv)$/i.test(f.name))
    if (ok.length < list.length) toast('Only .xlsx, .xls and .csv files are used.', 'info')
    setFiles(ok)
  }
  const onDrop = (e: DragEvent) => {
    e.preventDefault()
    setDrag(false)
    pick(e.dataTransfer.files)
  }

  return (
    <main className="page">
      <section className="card">
        <div className="card-head tight">
          <div>
            <h2>Zoho Books</h2>
            <p className="sub">Pull the latest data and build a new forecast run.</p>
          </div>
          <button className="btn" onClick={() => void checkZoho()} disabled={zoho === 'checking'}>
            Check connection
          </button>
        </div>
        {zoho && (
          <p className={`status-line ${zoho !== 'checking' && zoho !== 'unknown' && zoho.ok ? 'ok' : 'bad'}`}>
            {zoho === 'checking' ? (
              'Checking Zoho…'
            ) : zoho === 'unknown' ? (
              'Could not reach the forecast server.'
            ) : zoho.ok ? (
              <>
                <CheckCircle2 size={16} /> Zoho connected · {zoho.org_name || `org ${zoho.org_id}`}
              </>
            ) : (
              <>
                <CircleAlert size={16} /> {zoho.message}
              </>
            )}
          </p>
        )}
        <div className="oc-form">
          <label>
            Forecast week (a Friday)
            <input type="date" value={syncDate} onChange={(e) => setSyncDate(e.target.value)} />
          </label>
          <div className="action-cell">
            <button
              className="btn primary"
              disabled={syncing || !!busy}
              onClick={() => void sync(syncDate || undefined)}
            >
              <RefreshCw size={16} /> {syncing ? 'Syncing…' : 'Sync from Zoho'}
            </button>
          </div>
        </div>
        <p className="fine">
          Read-only on Zoho. Creates a new run and selects it. The date moves to the Friday on or before it.
        </p>
      </section>

      <section className="card">
        <div className="card-head">
          <div>
            <h2>Upload Zoho exports</h2>
            <p className="sub">
              Drop the Zoho Books files and the bank statement. Each report is recognised by its columns.
            </p>
          </div>
        </div>
        <div
          className={`dropzone ${drag ? 'drag' : ''}`}
          role="button"
          tabIndex={0}
          onClick={() => fileIn.current?.click()}
          onKeyDown={(e) => {
            if (e.key === 'Enter' || e.key === ' ') fileIn.current?.click()
          }}
          onDragOver={(e) => {
            e.preventDefault()
            setDrag(true)
          }}
          onDragLeave={() => setDrag(false)}
          onDrop={onDrop}
        >
          <FileUp size={26} />
          <div className="dz-title">Drop files here, or click to browse</div>
          <div className="dz-sub">
            Invoice Details, Bill Details, Sales Order Details, Purchase Order Details and bank statements (.xlsx, .xls,
            .csv)
          </div>
          <input
            ref={fileIn}
            type="file"
            multiple
            accept=".xlsx,.xls,.csv"
            hidden
            onChange={(e) => {
              pick(e.target.files)
              e.target.value = ''
            }}
          />
        </div>
        {files.length > 0 && (
          <ul className="file-tags">
            {files.map((f) => (
              <li key={f.name}>
                {f.name}
                <span>{Math.max(1, Math.round(f.size / 1024))} KB</span>
              </li>
            ))}
          </ul>
        )}
        <div className="oc-form three">
          <label>
            Week 1 opening cash ($)
            <input
              type="number"
              step="0.01"
              inputMode="decimal"
              value={opening}
              onChange={(e) => setOpening(e.target.value)}
              placeholder="Leave blank to use the data"
            />
          </label>
          <label>
            Forecast start Friday
            <input type="date" value={asOf} onChange={(e) => setAsOf(e.target.value)} />
          </label>
          <div className="action-cell">
            <button
              className="btn primary"
              disabled={!files.length || !asOf || !!busy}
              onClick={() =>
                void create('Building the forecast', () => autoRun(files, opening, asOf), 'Forecast generated.')
              }
            >
              Generate 52-week forecast
            </button>
          </div>
        </div>
      </section>
    </main>
  )
}
