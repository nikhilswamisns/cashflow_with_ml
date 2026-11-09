import { useQuery } from '@tanstack/react-query'
import { fetchHealth, fetchUser } from './api'
export const useHealth = () => useQuery({ queryKey: ['health'], queryFn: fetchHealth, staleTime: 60_000, retry: false })
export const useUser = () => useQuery({ queryKey: ['me'], queryFn: fetchUser, staleTime: Infinity })
