import { api } from '@/shared/api'
import type { Actions } from '@/features/actions/types'

export const fetchActions = (id: string) => api<Actions>(`/runs/${id}/actions`)
