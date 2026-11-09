import { lazy, Suspense } from 'react'
import { BrowserRouter, Navigate, Route, Routes, useLocation } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { ThemeProvider } from '@/shared/theme'
import { ToastProvider } from '@/shared/toast'
import { RunProvider } from '@/features/runs/RunProvider'
import { SyncProvider } from '@/features/sync/SyncProvider'
import { Shell } from '@/features/shell/Shell'
import { ErrorBoundary } from './ErrorBoundary'
// One chunk per page: the dashboard does not download the matrix or the JSON editor.
const DashboardPage = lazy(() =>
  import('@/features/dashboard/DashboardPage').then((m) => ({ default: m.DashboardPage })),
)
const MatrixPage = lazy(() => import('@/features/matrix/MatrixPage').then((m) => ({ default: m.MatrixPage })))
const RevenuePage = lazy(() => import('@/features/revenue/RevenuePage').then((m) => ({ default: m.RevenuePage })))
const DataSyncPage = lazy(() => import('@/features/sync/DataSyncPage').then((m) => ({ default: m.DataSyncPage })))
const AssumptionsPage = lazy(() =>
  import('@/features/config/AssumptionsPage').then((m) => ({ default: m.AssumptionsPage })),
)

const queryClient = new QueryClient({ defaultOptions: { queries: { staleTime: 60_000, refetchOnWindowFocus: false } } })

function Pages() {
  const { pathname } = useLocation()
  return (
    <ErrorBoundary resetKey={pathname}>
      <Suspense
        fallback={
          <main className="page">
            <div className="loading">Loading…</div>
          </main>
        }
      >
        <Routes>
          <Route element={<Shell />}>
            <Route index element={<DashboardPage />} />
            <Route path="matrix" element={<MatrixPage />} />
            <Route path="revenue" element={<RevenuePage />} />
            <Route path="data" element={<DataSyncPage />} />
            <Route path="assumptions" element={<AssumptionsPage />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Route>
        </Routes>
      </Suspense>
    </ErrorBoundary>
  )
}

export function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <ThemeProvider>
        <ToastProvider>
          <BrowserRouter basename="/ui3">
            <RunProvider>
              <SyncProvider>
                <Pages />
              </SyncProvider>
            </RunProvider>
          </BrowserRouter>
        </ToastProvider>
      </ThemeProvider>
    </QueryClientProvider>
  )
}
