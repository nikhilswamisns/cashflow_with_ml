import { api } from '@/shared/api'
import type { Health } from './types'
export const fetchUser = () => api<{ user: string | null }>('/auth/me')

export async function logout() {
  await api('/auth/logout', { method: 'POST' })
  location.href = '/login'
}

export const fetchHealth = () => api<Health>('/health')
