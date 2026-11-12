import { useState } from 'react'
import { BlockLoading } from '@/shared/ui/Loading'
import { Download } from 'lucide-react'
import { useMatrix } from '@/features/matrix/hooks'
import { exportUrl } from '@/features/runs/api'
import { useRun } from '@/features/runs/RunProvider'
import { MatrixTable } from '@/features/matrix/MatrixTable'
export function MatrixPage() {
  const { runId } = useRun()
  const { data, error, isPending } = useMatrix(runId)
  const [query, setQuery] = useState('')
  const [weeks, setWeeks] = useState(52)

  return (
    <main className="page">
      <section className="card matrix-card">
        <div className="card-head">
          <div>
            <h2>52-week cash flow matrix</h2>
            <p className="sub">
              Every cell is calculated from the Zoho data. Click an amount to see the line items behind it.
            </p>
          </div>
          <div className="controls">
            <input
              className="field"
              type="search"
              placeholder="Filter line item or code…"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              aria-label="Filter rows"
            />
            <select
              className="field"
              value={weeks}
              onChange={(e) => setWeeks(+e.target.value)}
              aria-label="Weeks shown"
            >
              <option value={52}>52 weeks</option>
              <option value={26}>26 weeks</option>
              <option value={13}>13 weeks</option>
            </select>
            <a className="btn" href={runId ? exportUrl(runId) : undefined}>
              <Download size={16} /> Download Excel
            </a>
          </div>
        </div>
        {error ? (
          <p className="insight warn">The matrix could not be loaded: {error.message}</p>
        ) : isPending || !data ? (
          <BlockLoading />
        ) : (
          <MatrixTable data={data} weeks={weeks} query={query} />
        )}
      </section>
    </main>
  )
}
