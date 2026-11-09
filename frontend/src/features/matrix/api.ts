import { api } from '@/shared/api'
import type { MatrixCell, MatrixData, MatrixRow, RowKind } from '@/features/matrix/types'
// Older runs have no `layout`; /ui2 then draws a fixed list of fields. Same list here, turned into the same row shape.
const LEGACY: [string, string, string, RowKind][] = [
  ['opening_cash', '', 'Opening Cash Position', 'total'],
  ['', '', 'REVENUES', 'section'],
  ['servpro_corporate', '1100.1', 'SERVPRO Corporate', 'line'],
  ['other_resellers', '1100.2', 'Other Resellers', 'line'],
  ['amazon', '1100.3', 'Amazon', 'line'],
  ['adjustments', '1101', 'Adjustments', 'line'],
  ['discount_given', '1102', 'Discount Given', 'line'],
  ['freight_billed', '1103', 'Freight Billed', 'line'],
  ['ar_collection', 'AR', 'A/R Collection', 'line'],
  ['total_revenue', '', 'Total Revenue', 'total'],
  ['', '', 'COGS', 'section'],
  ['cogs_standard', '3100', 'Cost of Goods Sold', 'line'],
  ['inbound_freight', '3101', 'Inbound Freight', 'line'],
  ['inbound_duty', '3102', 'Inbound Duty & Govt Fees', 'line'],
  ['total_cogs', '', 'Total COGS', 'total'],
  ['', '', 'OPERATIONS', 'section'],
  ['ops_amazon_fba', '2102', 'Amazon FBA Fees', 'line'],
  ['ops_ea_salaries', '2106', 'Operations Salaries', 'line'],
  ['ops_outbound_freight', '2107', 'Outbound Freight Costs', 'line'],
  ['total_operations', '', 'Total Operations', 'total'],
  ['gross_profit', '', 'GROSS PROFIT', 'gross'],
  ['total_marketing', '', 'Total Marketing', 'total'],
  ['total_selling', '', 'Total Selling', 'total'],
  ['total_finance_admin', '', 'Total Finance & Admin', 'total'],
  ['total_it', '', 'Total IT', 'total'],
  ['total_non_operating', '', 'Total Non-Operating', 'total'],
  ['cc_payment_due', '', 'Credit Card Payment Due', 'line'],
  ['loan_repayments', '', 'Loan Repayments', 'line'],
  ['cc_charges_deferred', '', 'CC Charges Deferred (non-cash)', 'line'],
  ['ending_cash', '', 'Ending Cash Position', 'ending'],
]
const cellAmount = (v: unknown) =>
  typeof v === 'number' ? v : v && typeof (v as MatrixCell).amount === 'number' ? (v as MatrixCell).amount : 0

export async function fetchMatrix(id: string): Promise<MatrixData> {
  const m = await api<{ weeks: MatrixData['weeks']; layout?: MatrixRow[] }>(`/runs/${id}/matrix`)
  if (m.layout) return { weeks: m.weeks, rows: m.layout }
  const rows: MatrixRow[] = LEGACY.map(([field, code, label, kind]) => ({
    kind,
    code,
    label,
    field: field || null,
    values: field ? m.weeks.map((w) => cellAmount(w[field])) : [],
  }))
  return { weeks: m.weeks, rows }
}
