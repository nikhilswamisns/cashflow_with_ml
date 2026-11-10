export interface KpiValues {
  opening_cash: number
  ending_cash: number
  lowest_cash: number
  lowest_week: string
  total_inflow: number
  total_outflow: number
  total_ar: number
  total_ap: number
  net_change: number
  avg_weekly_net: number
  as_of: string
}

export interface Receipts {
  docs: number[]
  runrate: number[]
  forecast: number[]
}

export interface MlTiming {
  cash_ml: number[]
  p10: number[]
  p90: number[]
}

export interface ActualPoint {
  date: string // ISO date
  balance: number
  kind: 'week_end' | 'today'
}
/** Actual cash from Zoho books: past Fridays (HISTORY_WEEKS before the run's first week too) plus today's balance. */
export interface Actuals {
  points: ActualPoint[]
  firstWeek: string // ISO date of the run's first week-ending Friday
  historyWeeks: number
}
export interface TrackRow {
  week_ending: string
  rules: number
  ml: number | null
  p10: number | null
  p90: number | null
  actual: number | null
  gap_rules?: number
  gap_ml?: number | null
  closer?: 'ml' | 'rules'
  run_created: string
}
export interface Track {
  rows: TrackRow[]
  summary: { weeks_scored: number; avg_miss_rules: number | null; avg_miss_ml: number | null }
  horizon_weeks: number
  rule: string
}

export interface DashboardData {
  labels: string[] // week-ending Friday as "MM-DD"
  kpis: KpiValues
  cash_rules: number[] // blue line: ALWAYS rules-only (from /compare), never the saved run
  rulesFromSavedRun: boolean // true only when /compare failed and we fell back to the saved run (may be ML-timed)
  ml: MlTiming | null // null while loading or if unavailable
  receipts: Receipts | null
  actuals: Actuals | null // null while loading, or when this server cannot read Zoho
  floor: number | null // minimum cash floor; null = none configured on the server
  ar: number[]
  ap: number[]
  inflows: number[]
  outflows: number[]
  streams: Record<string, number[]>
}
