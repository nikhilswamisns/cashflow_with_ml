import { api } from '@/shared/api'
import type { NewRun, OpeningCash, ZohoStatus } from '@/features/sync/types'
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
export function runFromSnapshot(file: File) {
  const fd = new FormData()
  fd.append('file', file)
  return api<NewRun>('/forecast/run-from-snapshot', { method: 'POST', body: fd })
}
export const quickDemo = () => api<NewRun>('/forecast/quick-demo', { method: 'POST' })
export const openArchive = (id: string) =>
  api<{ opened?: boolean; folder?: string }>(`/runs/${id}/open-archive`, { method: 'POST' })
// zoho/status makes a live call to Zoho, so it only runs when the user asks
export const fetchZohoStatus = () => api<ZohoStatus>('/zoho/status')
export const fetchOpeningCash = (id: string) => api<OpeningCash>(`/runs/${id}/opening-cash`)
export const saveOpeningCash = (runId: string, amount: number, asOf: string) =>
  api('/opening-cash', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ amount, as_of_date: asOf, run_id: runId, entered_by: 'UI' }),
  })
