import { useQuery } from '@tanstack/react-query'
import { fetchRevenueForecast } from './api'
export const useRevenueForecast = () =>
  useQuery({ queryKey: ['revenue-forecast'], queryFn: fetchRevenueForecast, retry: false })
