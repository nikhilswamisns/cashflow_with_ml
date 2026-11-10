import { useQuery } from '@tanstack/react-query'
import { fetchActions } from '@/features/actions/api'

export const useActions = (runId: string) =>
  useQuery({ queryKey: ['actions', runId], queryFn: () => fetchActions(runId), enabled: !!runId, retry: false })
