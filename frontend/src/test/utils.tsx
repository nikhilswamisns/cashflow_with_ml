import type { ReactElement } from 'react'
import { render } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { ToastProvider } from '@/shared/toast'

export const newClient = () => new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: Infinity } } })

/** Render with the providers every feature expects. */
export function renderApp(ui: ReactElement, { route = '/', client = newClient() } = {}) {
  return render(
    <QueryClientProvider client={client}>
      <ToastProvider>
        <MemoryRouter initialEntries={[route]}>{ui}</MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  )
}

/** Stub fetch with a map of "METHOD /path" -> JSON body (or a Response). Unknown routes answer 404. */
export function stubApi(routes: Record<string, unknown>) {
  const fn = vi.fn(async (url: string, init?: RequestInit) => {
    const key = `${init?.method ?? 'GET'} ${String(url).replace(/^\/api/, '')}`
    if (!(key in routes)) return new Response(JSON.stringify({ detail: 'not found' }), { status: 404 })
    const v = routes[key]
    return v instanceof Response ? v : new Response(JSON.stringify(v), { status: 200 })
  })
  vi.stubGlobal('fetch', fn)
  return fn
}
