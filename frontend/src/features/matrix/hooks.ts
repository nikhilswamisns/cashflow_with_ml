import { useQuery } from '@tanstack/react-query'
import { fetchMatrix } from './api'
export const useMatrix = (runId: string) =>
  useQuery({ queryKey: ['matrix', runId], queryFn: () => fetchMatrix(runId), enabled: !!runId })
