// The ONLY file that knows the API shapes. Everything is read-only here.
import { api } from './api'
import type { Answer, Health, NewRun, ZohoStatus, Kpis, MatrixCell, MatrixData, MatrixRow, MlTiming, OpeningCash, Receipts, RowKind, RunInfo } from './types'

interface RunRow { run_id: string; run_date: string; created_at: string }
interface Analytics {
  labels: string[]; cash_trajectory: number[]; inflows: number[]; outflows: number[]
  revenue_streams: Record<string, number[]>; ar_ap: { ar_trajectory: number[]; ap_trajectory: number[] }; kpis: Kpis
}
interface Compare { ending_cash_rules: number[]; ending_cash_ml: number[]; bands: { p10: number[]; p90: number[] } }
interface Outlook { documents: number[]; run_rate: number[]; forecast_added: number[] }

const fmtDate = (iso: string) => new Date(iso.length === 10 ? iso + 'T00:00:00' : iso)
  .toLocaleDateString('en-US', { day: 'numeric', month: 'short', year: 'numeric' })
const fmtStamp = (iso: string) => new Date(iso)
  .toLocaleString('en-US', { day: 'numeric', month: 'short', hour: 'numeric', minute: '2-digit', hour12: false })

export async function fetchRuns(): Promise<RunInfo[]> {
  const rows = await api<RunRow[]>('/runs')
  return rows.map((r) => ({ id: r.run_id, label: fmtDate(r.run_date), syncedLabel: `Run created ${fmtStamp(r.created_at)}` }))
}

export const fetchAnalytics = (id: string) => api<Analytics>(`/runs/${id}/analytics`)

// about 4 s the first time on the server (cached after), so callers load it separately from the rest
export async function fetchMl(id: string): Promise<{ rules: number[]; ml: MlTiming }> {
  const c = await api<Compare>(`/ml/runs/${id}/compare`)
  return { rules: c.ending_cash_rules, ml: { cash_ml: c.ending_cash_ml, p10: c.bands.p10, p90: c.bands.p90 } }
}

export async function fetchReceipts(id: string): Promise<Receipts> {
  const o = await api<Outlook>(`/ml/runs/${id}/receipts-outlook`)
  return { docs: o.documents, runrate: o.run_rate, forecast: o.forecast_added }
}

// Older runs have no `layout`; /ui2 then draws a fixed list of fields. Same list here, turned into the same row shape.
const LEGACY: [string, string, string, RowKind][] = [
  ['opening_cash', '', 'Opening Cash Position', 'total'], ['', '', 'REVENUES', 'section'],
  ['servpro_corporate', '1100.1', 'SERVPRO Corporate', 'line'], ['other_resellers', '1100.2', 'Other Resellers', 'line'], ['amazon', '1100.3', 'Amazon', 'line'],
  ['adjustments', '1101', 'Adjustments', 'line'], ['discount_given', '1102', 'Discount Given', 'line'], ['freight_billed', '1103', 'Freight Billed', 'line'],
  ['ar_collection', 'AR', 'A/R Collection', 'line'], ['total_revenue', '', 'Total Revenue', 'total'],
  ['', '', 'COGS', 'section'], ['cogs_standard', '3100', 'Cost of Goods Sold', 'line'], ['inbound_freight', '3101', 'Inbound Freight', 'line'],
  ['inbound_duty', '3102', 'Inbound Duty & Govt Fees', 'line'], ['total_cogs', '', 'Total COGS', 'total'],
  ['', '', 'OPERATIONS', 'section'], ['ops_amazon_fba', '2102', 'Amazon FBA Fees', 'line'], ['ops_ea_salaries', '2106', 'Operations Salaries', 'line'],
  ['ops_outbound_freight', '2107', 'Outbound Freight Costs', 'line'], ['total_operations', '', 'Total Operations', 'total'],
  ['gross_profit', '', 'GROSS PROFIT', 'gross'], ['total_marketing', '', 'Total Marketing', 'total'], ['total_selling', '', 'Total Selling', 'total'],
  ['total_finance_admin', '', 'Total Finance & Admin', 'total'], ['total_it', '', 'Total IT', 'total'], ['total_non_operating', '', 'Total Non-Operating', 'total'],
  ['cc_payment_due', '', 'Credit Card Payment Due', 'line'], ['loan_repayments', '', 'Loan Repayments', 'line'],
  ['cc_charges_deferred', '', 'CC Charges Deferred (non-cash)', 'line'], ['ending_cash', '', 'Ending Cash Position', 'ending'],
]
const cellAmount = (v: unknown) => typeof v === 'number' ? v : (v && typeof (v as MatrixCell).amount === 'number' ? (v as MatrixCell).amount : 0)

export async function fetchMatrix(id: string): Promise<MatrixData> {
  const m = await api<{ weeks: MatrixData['weeks']; layout?: MatrixRow[] }>(`/runs/${id}/matrix`)
  if (m.layout) return { weeks: m.weeks, rows: m.layout }
  const rows: MatrixRow[] = LEGACY.map(([field, code, label, kind]) => ({
    kind, code, label, field: field || null, values: field ? m.weeks.map((w) => cellAmount(w[field])) : [],
  }))
  return { weeks: m.weeks, rows }
}

export const fetchUser = () => api<{ user: string | null }>('/auth/me')

export async function logout() {
  await api('/auth/logout', { method: 'POST' })
  location.href = '/login'
}

// ---- actions (these write: sync creates a run, opening cash changes one) ----
export const syncZoho = (runDate?: string) =>
  api<NewRun>(`/forecast/sync-zoho-live${runDate ? `?run_date=${encodeURIComponent(runDate)}` : ''}`, { method: 'POST' })
export function autoRun(files: File[], openingCash: string, asOf: string) {
  const fd = new FormData()
  files.forEach((f) => fd.append('files', f))
  if (openingCash) fd.append('opening_cash', openingCash)
  if (asOf) fd.append('as_of_date', asOf)
  return api<NewRun>('/forecast/auto-run', { method: 'POST', body: fd })
}
export function runFromSnapshot(file: File) {
  const fd = new FormData(); fd.append('file', file)
  return api<NewRun>('/forecast/run-from-snapshot', { method: 'POST', body: fd })
}
export const openArchive = (id: string) => api<{ opened?: boolean; folder?: string }>(`/runs/${id}/open-archive`, { method: 'POST' })
// zoho/status makes a live call to Zoho, so it only runs when the user asks
export const fetchZohoStatus = () => api<ZohoStatus>('/zoho/status')
export const fetchHealth = () => api<Health>('/health')
export const exportUrl = (id: string) => `/api/runs/${id}/export/xlsx`
export const fetchOpeningCash = (id: string) => api<OpeningCash>(`/runs/${id}/opening-cash`)
export const saveOpeningCash = (runId: string, amount: number, asOf: string) =>
  api('/opening-cash', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ amount, as_of_date: asOf, run_id: runId, entered_by: 'UI' }) })

// Step A placeholder until the AI backend exists (separate track).
export async function askQuestion(_runId: string, _q: string): Promise<Answer> {
  return {
    html: 'In the real build this runs a lookup on the payment history and answers with the figures and the run it used. This sample only has the first answer.',
    source: 'Sample reply',
  }
}
