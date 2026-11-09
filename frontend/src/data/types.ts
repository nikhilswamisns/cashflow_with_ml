// What the components see. data/source.ts maps the real API responses onto these types.
export interface Kpis {
  opening_cash: number; ending_cash: number; lowest_cash: number; lowest_week: string
  total_inflow: number; total_outflow: number; total_ar: number; total_ap: number
  net_change: number; avg_weekly_net: number; as_of: string
}
export interface Receipts { docs: number[]; runrate: number[]; forecast: number[] }
export interface MlTiming { cash_ml: number[]; p10: number[]; p90: number[] }

export interface DashboardData {
  labels: string[]               // week-ending Friday as "MM-DD"
  kpis: Kpis
  cash_rules: number[]           // blue line: ALWAYS rules-only (from /compare), never the saved run
  rulesFromSavedRun: boolean     // true only when /compare failed and we fell back to the saved run (may be ML-timed)
  ml: MlTiming | null            // null while loading or if unavailable
  receipts: Receipts | null
  floor: number | null           // minimum cash floor; null = none configured on the server
  ar: number[]; ap: number[]
  inflows: number[]; outflows: number[]
  streams: Record<string, number[]>
}

export interface RunInfo { id: string; label: string; syncedLabel: string }
export interface Answer { html: string; source: string }

export interface OpeningCash {
  run_date: string
  accounts: { name: string; balance: number }[]
  zoho_cash: number
  manual_adjustments: { label: string; amount: number }[]
  opening_cash: number
  override: number | null
  override_as_of: string | null
}

export interface LineItem { label?: string; raw_ref?: string | null; amount: number; confidence?: string | null }
export interface MatrixCell { amount: number; line_items?: LineItem[] }
export type RowKind = 'section' | 'group' | 'line' | 'total' | 'opening' | 'gross' | 'ending'
export interface MatrixRow { kind: RowKind; code: string; label: string; field: string | null; values: number[] }
export interface MatrixWeek { week_ending_friday: string; [field: string]: unknown }
export interface MatrixData { weeks: MatrixWeek[]; rows: MatrixRow[] }

export interface ZohoStatus { ok: boolean; org_id?: string; org_name?: string; message: string }
export interface HealthCheck { name: string; ok: boolean; required: boolean; detail: string; fix: string }
export interface Health { status: 'ok' | 'degraded' | 'broken' | string; checks: HealthCheck[] }
export interface NewRun { run_id: string; live_opening_cash?: number; archive_folder?: string | null; detected_files?: { filename: string; source: string; count?: number; error?: string }[] }
