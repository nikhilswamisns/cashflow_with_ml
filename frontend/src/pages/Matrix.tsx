import { useState } from 'react'
import { useOutletContext } from 'react-router-dom'
import { Download } from 'lucide-react'
import { useMatrix } from '../data/hooks'
import { exportUrl } from '../data/source'
import type { ShellCtx } from '../components/Shell'
import { MatrixTable } from '../components/MatrixTable'

export function Matrix() {
  const { runId } = useOutletContext<ShellCtx>()
  const { data, error, isPending } = useMatrix(runId)
  const [query, setQuery] = useState('')
  const [weeks, setWeeks] = useState(52)

  return (
    <main className="page">
      <section className="card matrix-card">
        <div className="card-head">
          <div>
            <h2>52-week cash flow matrix</h2>
            <p className="sub">Every cell is calculated from the Zoho data. Click an amount to see the line items behind it.</p>
          </div>
          <div className="controls">
            <input className="field" type="search" placeholder="Filter line item or code…" value={query} onChange={(e) => setQuery(e.target.value)} aria-label="Filter rows" />
            <select className="field" value={weeks} onChange={(e) => setWeeks(+e.target.value)} aria-label="Weeks shown">
              <option value={52}>52 weeks</option><option value={26}>26 weeks</option><option value={13}>13 weeks</option>
            </select>
            <a className="btn" href={runId ? exportUrl(runId) : undefined}><Download size={16} /> Download Excel</a>
          </div>
        </div>
        {error ? <p className="insight warn">The matrix could not be loaded: {error.message}</p>
          : isPending || !data ? <div className="chart chart-wait"><span>Loading the matrix…</span></div>
          : <MatrixTable data={data} weeks={weeks} query={query} />}
      </section>
    </main>
  )
}
