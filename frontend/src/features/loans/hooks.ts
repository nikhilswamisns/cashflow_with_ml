import { useQuery } from '@tanstack/react-query'
import { fetchLoans } from '@/features/loans/api'

export const useLoans = () => useQuery({ queryKey: ['loans'], queryFn: fetchLoans, staleTime: 60_000, retry: false })
