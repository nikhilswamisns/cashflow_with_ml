import { api } from '@/shared/api'
import type { RunInfo } from '@/features/runs/types'
interface RunRow {
  run_id: string
  run_date: string
  created_at: string
}

const fmtDate = (iso: string) =>
  new Date(iso.length === 10 ? iso + 'T00:00:00' : iso).toLocaleDateString('en-US', {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
  })
const fmtStamp = (iso: string) =>
  new Date(iso).toLocaleString('en-US', {
    day: 'numeric',
    month: 'short',
    hour: 'numeric',
    minute: '2-digit',
    hour12: false,
  })

export async function fetchRuns(): Promise<RunInfo[]> {
  const rows = await api<RunRow[]>('/runs')
  return rows.map((r) => ({
    id: r.run_id,
    label: fmtDate(r.run_date),
    syncedLabel: `Run created ${fmtStamp(r.created_at)}`,
  }))
}

export const exportUrl = (id: string) => `/api/runs/${id}/export/xlsx`
