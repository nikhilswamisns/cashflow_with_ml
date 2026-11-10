import { api } from '@/shared/api'
import type { NewRun, ZohoStatus } from '@/features/sync/types'
export const syncZoho = (runDate?: string) =>
  api<NewRun>(`/forecast/sync-zoho-live${runDate ? `?run_date=${encodeURIComponent(runDate)}` : ''}`, {
    method: 'POST',
  })
export function autoRun(files: File[], openingCash: string, asOf: string) {
  const fd = new FormData()
  files.forEach((f) => fd.append('files', f))
  if (openingCash) fd.append('opening_cash', openingCash)
  if (asOf) fd.append('as_of_date', asOf)
  return api<NewRun>('/forecast/auto-run', { method: 'POST', body: fd })
}
// zoho/status makes a live call to Zoho, so it only runs when the user asks
export const fetchZohoStatus = () => api<ZohoStatus>('/zoho/status')
