import { api } from '@/shared/api'
import type { WorkingCapital } from '@/features/workingcapital/types'

export const fetchWorkingCapital = (id: string) => api<WorkingCapital>(`/runs/${id}/working-capital`)
