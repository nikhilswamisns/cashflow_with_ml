import { api } from '@/shared/api'
import type { RevenueForecast } from '@/features/revenue/types'
export const fetchRevenueForecast = () => api<RevenueForecast>('/ml/revenue-forecast')
