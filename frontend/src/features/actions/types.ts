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
