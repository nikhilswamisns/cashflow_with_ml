import { useRef, useState, type DragEvent } from 'react'
import { useOutletContext } from 'react-router-dom'
import { CheckCircle2, CircleAlert, FileUp, RefreshCw } from 'lucide-react'
import { useQueryClient } from '@tanstack/react-query'
import { autoRun, fetchZohoStatus, openArchive, runFromSnapshot } from '../data/source'
import { useHealth } from '../data/hooks'
import type { ZohoStatus } from '../data/types'
import type { ShellCtx } from '../components/Shell'
import { useDismissToast, useToast } from '../lib/toast'

const iso = (d: Date) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
function fridayOnOrBefore(d = new Date()) { const x = new Date(d); x.setDate(x.getDate() - ((x.getDay() + 2) % 7)); return iso(x) }

export function DataSync() {
  const { runId, afterRun, sync, syncing } = useOutletContext<ShellCtx>()
  const toast = useToast(); const dismiss = useDismissToast()
  const qc = useQueryClient()
  const health = useHealth()
  const [zoho, setZoho] = useState<ZohoStatus | 'checking' | 'unknown' | null>(null)
  const [syncDate, setSyncDate] = useState(fridayOnOrBefore())
  const [files, setFiles] = useState<File[]>([])
  const [drag, setDrag] = useState(false)
  const [opening, setOpening] = useState('')
  const [asOf, setAsOf] = useState(fridayOnOrBefore())
  const [busy, setBusy] = useState('')
  const fileIn = useRef<HTMLInputElement>(null)
  const snapIn = useRef<HTMLInputElement>(null)

  async function checkZoho() {
    setZoho('checking')
    try { setZoho(await fetchZohoStatus()) } catch { setZoho('unknown') }
  }

  async function create(label: string, work: () => Promise<{ run_id: string }>, done: string) {
    if (busy) return
    setBusy(label)
    const wait = toast(`${label}…`, 'info', 0)
    try { const r = await work(); await afterRun(r.run_id); toast(done, 'ok') }
    catch (e) { toast(`${label}: ${(e as Error).message}`, 'error', 8000) }
    finally { dismiss(wait); setBusy('') }
  }

  const pick = (list: FileList | null) => {
    if (!list) return
    const ok = [...list].filter((f) => /\.(xlsx|xls|csv)$/i.test(f.name))
    if (ok.length < list.length) toast('Only .xlsx, .xls and .csv files are used.', 'info')
    setFiles(ok)
  }
  const onDrop = (e: DragEvent) => { e.preventDefault(); setDrag(false); pick(e.dataTransfer.files) }

  async function archive() {
    try {
      const j = await openArchive(runId)
      toast(j.opened ? 'Archive folder opened.' : `Archive folder: ${j.folder}`, 'info', 8000)
    } catch (e) { toast((e as Error).message, 'error') }
  }

  return (
    <main className="page">
      <section className="grid2">
        <article className="card">
          <div className="card-head tight"><div><h2>Zoho Books</h2><p className="sub">Pull the latest data and build a new forecast run.</p></div>
            <button className="btn" onClick={() => void checkZoho()} disabled={zoho === 'checking'}>Check connection</button></div>
          {zoho && (
            <p className={`status-line ${zoho !== 'checking' && zoho !== 'unknown' && zoho.ok ? 'ok' : 'bad'}`}>
              {zoho === 'checking' ? 'Checking Zoho…' : zoho === 'unknown' ? 'Could not reach the forecast server.'
                : zoho.ok ? <><CheckCircle2 size={16} /> Zoho connected · {zoho.org_name || `org ${zoho.org_id}`}</> : <><CircleAlert size={16} /> {zoho.message}</>}
            </p>
          )}
          <div className="oc-form">
            <label>Forecast week (a Friday)<input type="date" value={syncDate} onChange={(e) => setSyncDate(e.target.value)} /></label>
            <div className="action-cell"><button className="btn primary" disabled={syncing || !!busy} onClick={() => void sync(syncDate || undefined)}><RefreshCw size={16} /> {syncing ? 'Syncing…' : 'Sync from Zoho'}</button></div>
          </div>
          <p className="fine">Read-only on Zoho. Creates a new run and selects it. The date moves to the Friday on or before it.</p>
        </article>

        <article className="card">
          <div className="card-head tight"><div><h2>Server health</h2><p className="sub">Files and settings the dashboard needs.</p></div>
            <button className="btn" onClick={() => void qc.invalidateQueries({ queryKey: ['health'] })}>Re-check</button></div>
          {health.isError && <p className="status-line bad"><CircleAlert size={16} /> Health check could not be read.</p>}
          <ul className="health-list">
            {(health.data?.checks ?? []).map((c) => (
              <li key={c.name} className={c.ok ? 'ok' : c.required ? 'bad' : 'warn'}>
                {c.ok ? <CheckCircle2 size={15} /> : <CircleAlert size={15} />}<b>{c.name}</b><span>{c.detail}{!c.ok && c.fix ? `. ${c.fix}` : ''}</span>
              </li>
            ))}
          </ul>
        </article>
      </section>

      <section className="card">
        <div className="card-head"><div><h2>Upload Zoho exports</h2><p className="sub">Drop the Zoho Books files and the bank statement. Each report is recognised by its columns.</p></div></div>
        <div className={`dropzone ${drag ? 'drag' : ''}`} role="button" tabIndex={0}
          onClick={() => fileIn.current?.click()} onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') fileIn.current?.click() }}
          onDragOver={(e) => { e.preventDefault(); setDrag(true) }} onDragLeave={() => setDrag(false)} onDrop={onDrop}>
          <FileUp size={26} />
          <div className="dz-title">Drop files here, or click to browse</div>
          <div className="dz-sub">Invoice Details, Bill Details, Sales Order Details, Purchase Order Details and bank statements (.xlsx, .xls, .csv)</div>
          <input ref={fileIn} type="file" multiple accept=".xlsx,.xls,.csv" hidden onChange={(e) => { pick(e.target.files); e.target.value = '' }} />
        </div>
        {files.length > 0 && (
          <ul className="file-tags">{files.map((f) => <li key={f.name}>{f.name}<span>{Math.max(1, Math.round(f.size / 1024))} KB</span></li>)}</ul>
        )}
        <div className="oc-form three">
          <label>Week 1 opening cash ($)<input type="number" step="0.01" inputMode="decimal" value={opening} onChange={(e) => setOpening(e.target.value)} placeholder="Leave blank to use the data" /></label>
          <label>Forecast start Friday<input type="date" value={asOf} onChange={(e) => setAsOf(e.target.value)} /></label>
          <div className="action-cell">
            <button className="btn primary" disabled={!files.length || !asOf || !!busy}
              onClick={() => void create('Building the forecast', () => autoRun(files, opening, asOf), 'Forecast generated.')}>Generate 52-week forecast</button>
          </div>
        </div>
      </section>

      <section className="card">
        <div className="card-head"><div><h2>Other ways to create or inspect a run</h2></div></div>
        <div className="tool-row">
          <div><b>Re-run from a saved snapshot</b><p className="sub">Rebuild a forecast from an archived Zoho snapshot file (.json).</p></div>
          <button className="btn" disabled={!!busy} onClick={() => snapIn.current?.click()}><FileUp size={16} /> Choose snapshot</button>
          <input ref={snapIn} type="file" accept=".json,application/json" hidden onChange={(e) => {
            const f = e.target.files?.[0]; e.target.value = ''
            if (f) void create('Re-running from the snapshot', () => runFromSnapshot(f), `Forecast rebuilt from ${f.name}.`)
          }} />
        </div>
        <div className="tool-row">
          <div><b>Zoho data folder for the selected run</b><p className="sub">Opens the archive folder if the server runs on your own PC; otherwise shows its path.</p></div>
          <button className="btn" disabled={!runId} onClick={() => void archive()}>Show archive folder</button>
        </div>
      </section>
    </main>
  )
}
