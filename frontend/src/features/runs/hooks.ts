import { useQuery } from '@tanstack/react-query'
import { fetchRuns } from '@/features/runs/api'
export const useRuns = () => useQuery({ queryKey: ['runs'], queryFn: fetchRuns })
