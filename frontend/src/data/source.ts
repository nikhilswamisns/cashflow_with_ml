// The ONLY file that knows the API shapes. Everything is read-only here.
import { api } from './api'
import type { Answer, Kpis, MlTiming, Receipts, RunInfo } from './types'

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

export const fetchUser = () => api<{ user: string | null }>('/auth/me')

export async function logout() {
  await api('/auth/logout', { method: 'POST' })
  location.href = '/login'
}

// Step A placeholder until the AI backend exists (separate track).
export async function askQuestion(_runId: string, _q: string): Promise<Answer> {
  return {
    html: 'In the real build this runs a lookup on the payment history and answers with the figures and the run it used. This sample only has the first answer.',
    source: 'Sample reply',
  }
}
