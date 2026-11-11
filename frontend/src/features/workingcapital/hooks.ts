import { useQuery } from '@tanstack/react-query'
import { fetchWorkingCapital } from '@/features/workingcapital/api'

export const useWorkingCapital = (runId: string) =>
  useQuery({
    queryKey: ['working-capital', runId],
    queryFn: () => fetchWorkingCapital(runId),
    enabled: !!runId,
    retry: false,
  })
