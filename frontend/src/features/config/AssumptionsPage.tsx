import { useState } from 'react'
import { BlockLoading } from '@/shared/ui/Loading'
import { useQuery } from '@tanstack/react-query'
import { fetchConfig } from '@/features/config/api'
import { useSearchParams } from 'react-router-dom'
import type { ConfigTable, TableKey } from '@/features/config/types'
import { ConfigForm } from '@/features/config/ConfigForm'
import { LoansEditor } from '@/features/loans/LoansEditor'
import { useLoans } from '@/features/loans/hooks'

const TABLES: [TableKey, string][] = [
  ['assumptions', 'Assumptions & Rules'],
  ['loans', 'Loans & credit lines'],
  ['corporate_accounts', 'Corporate Accounts'],
  ['freight_duty_vendors', 'Freight & Duty Vendors'],
  ['cc_category_coa_map', 'Credit Card Category Map'],
]

// Every table is a form with a Raw JSON view, except loans, which has its own editor. Nothing is saved until you press the button. Nothing is saved until you press the button.
export function AssumptionsPage() {
  const [params] = useSearchParams()
  const [table, setTable] = useState<TableKey>(params.get('table') === 'loans' ? 'loans' : 'assumptions')
  const loans = useLoans()
  // always re-read the file when you open a table: you are about to edit the live value
  const { data, error, isFetching, dataUpdatedAt } = useQuery({
    queryKey: ['config', table],
    queryFn: () => fetchConfig(table as ConfigTable),
    enabled: table !== 'loans',
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
            onChange={(e) => setTable(e.target.value as TableKey)}
            aria-label="Table"
          >
            {TABLES.map(([k, l]) => (
              <option key={k} value={k}>
                {l}
              </option>
            ))}
          </select>
        </div>
        {table === 'loans' ? (
          loans.data ? (
            <LoansEditor key={loans.dataUpdatedAt} saved={loans.data} />
          ) : loans.error ? (
            <p className="insight warn">Loans could not be loaded: {loans.error.message}</p>
          ) : (
            <BlockLoading />
          )
        ) : error ? (
          <p className="insight warn">This table could not be loaded: {error.message}</p>
        ) : !data || (isFetching && !dataUpdatedAt) ? (
          <BlockLoading tall />
        ) : (
          <ConfigForm key={`${table}:${dataUpdatedAt}`} table={table} saved={data} />
        )}
      </section>
    </main>
  )
}
