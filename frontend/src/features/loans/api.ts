import { api } from '@/shared/api'
import type { Facility, Loans } from '@/features/loans/types'

export const fetchLoans = () => api<Loans>('/loans')
export const saveLoans = (facilities: Facility[]) =>
  api<Loans>('/loans', {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ facilities }),
  })
