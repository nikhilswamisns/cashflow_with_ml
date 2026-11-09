import { api } from '@/shared/api'
import type { ConfigTable } from '@/features/config/types'
export const fetchConfig = (table: ConfigTable) => api<Record<string, unknown>>(`/config/${table}`)
// writes the server's config file and clears its cache, exactly like /ui2's "Save & Invalidate Cache"
export const saveConfig = (table: ConfigTable, body: unknown) =>
  api<{ message: string }>(`/config/${table}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
