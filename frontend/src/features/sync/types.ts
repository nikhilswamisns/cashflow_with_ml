export interface ZohoStatus {
  ok: boolean
  org_id?: string
  org_name?: string
  message: string
}

export interface NewRun {
  run_id: string
  live_opening_cash?: number
  archive_folder?: string | null
  detected_files?: { filename: string; source: string; count?: number; error?: string }[]
}

export interface OpeningCash {
  run_date: string
  accounts: { name: string; balance: number }[]
  zoho_cash: number
  manual_adjustments: { label: string; amount: number }[]
  opening_cash: number
  override: number | null
  override_as_of: string | null
}
