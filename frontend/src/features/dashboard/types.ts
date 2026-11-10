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
  kind: 'start' | 'week_end' | 'today'
}
/** Actual cash from Zoho books: the balance on the day the run was made, at each past Friday, and today. */
export interface Actuals {
  points: ActualPoint[]
  startDate: string // ISO date the run was made
}
export interface ActionItem {
  number: string | null
  party: string | null
  due_date: string
  days_overdue: number
  days_until_due?: number
  amount: number
}
export interface Actions {
  as_of: string
  window_days: number
  invoices: { count: number; total: number; items: ActionItem[] }
  bills: { count: number; total: number; overdue_count: number; overdue_total: number; items: ActionItem[] }
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
