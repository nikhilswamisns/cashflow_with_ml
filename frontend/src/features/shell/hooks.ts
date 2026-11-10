import { useQuery } from '@tanstack/react-query'
import { fetchUser } from './api'
export const useUser = () => useQuery({ queryKey: ['me'], queryFn: fetchUser, staleTime: Infinity })
