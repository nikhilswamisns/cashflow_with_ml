import { api } from '@/shared/api'
import type { Actuals, KpiValues, MlTiming, Receipts, Track } from '@/features/dashboard/types'
interface Analytics {
  labels: string[]
  cash_trajectory: number[]
  inflows: number[]
  outflows: number[]
  revenue_streams: Record<string, number[]>
  ar_ap: { ar_trajectory: number[]; ap_trajectory: number[] }
  kpis: KpiValues
}
interface Compare {
  ending_cash_rules: number[]
  ending_cash_ml: number[]
  bands: { p10: number[]; p90: number[] }
}
interface Outlook {
  documents: number[]
  run_rate: number[]
  forecast_added: number[]
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

interface ActualsResponse {
  points: Actuals['points']
  first_week: string
  history_weeks: number
}
// reads Zoho on the server (cached there for 10 minutes); 503 when the server has no Zoho access
export async function fetchActuals(id: string): Promise<Actuals> {
  const a = await api<ActualsResponse>(`/ml/runs/${id}/actuals`)
  return { points: a.points, firstWeek: a.first_week, historyWeeks: a.history_weeks }
}
export const fetchTrack = () => api<Track>('/ml/forecast-track')
