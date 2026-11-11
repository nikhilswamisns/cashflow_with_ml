export interface Bucket {
  label: string
  amount: number
  count: number
  share: number
}
export interface Aging {
  total: number
  count: number
  missing_due_date: number
  buckets: Bucket[]
}
export interface Shares {
  total: number
  top: { party: string; amount: number; share: number }[]
  top_share: number
  focus_name: string | null
  focus_amount: number
  focus_share: number
}
export interface WorkingCapital {
  as_of: string
  window_days: number
  ar: Aging
  ap: Aging
  dso: number | null
  dpo: number | null
  sales_90: number | null
  cogs_90: number | null
  flows_available: boolean
  concentration: { ar: Shares; sales: Shares | null }
}
