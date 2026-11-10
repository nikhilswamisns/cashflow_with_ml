import { api } from '@/shared/api'
export const fetchUser = () => api<{ user: string | null }>('/auth/me')

export async function logout() {
  await api('/auth/logout', { method: 'POST' })
  location.href = '/login'
}
