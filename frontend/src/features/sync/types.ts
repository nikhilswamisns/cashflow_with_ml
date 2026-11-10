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
