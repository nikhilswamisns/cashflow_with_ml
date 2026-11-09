// Thin fetch wrapper: same origin, session cookie, and any 401 sends the user to the login page.
export class ApiError extends Error {
  constructor(public status: number, message: string) { super(message) }
}

export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`/api${path}`, { credentials: 'same-origin', ...init })
  if (res.status === 401 && !path.startsWith('/auth/')) {
    location.href = `/login?next=${encodeURIComponent(location.pathname)}`
    throw new ApiError(401, 'Not logged in')
  }
  if (!res.ok) throw new ApiError(res.status, `${path} failed (${res.status})`)
  return res.json() as Promise<T>
}
