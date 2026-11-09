import '@fontsource-variable/geist'
import '@fontsource-variable/geist-mono'
import './styles.css'
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter, Route, Routes } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { ThemeProvider } from './lib/theme'
import { Shell } from './components/Shell'
import { Dashboard } from './pages/Dashboard'
import { Placeholder } from './pages/Placeholder'

const qc = new QueryClient({ defaultOptions: { queries: { staleTime: 60_000, refetchOnWindowFocus: false } } })
const PAGES: [string, string][] = [['matrix', 'Cash forecast'], ['receivables', 'Receivables & payables'], ['revenue', 'Revenue forecast'], ['ask', 'Ask Gutster'], ['data', 'Data & sync'], ['assumptions', 'Assumptions']]

// Chart text is measured on first draw, so load both fonts first (otherwise the "$" on axes gets clipped).
const fonts = Promise.all([
  document.fonts.load('500 12px "Geist Mono Variable"'), document.fonts.load('400 12px "Geist Mono Variable"'),
  document.fonts.load('500 14px "Geist Variable"'), document.fonts.load('650 14px "Geist Variable"'),
]).catch(() => {})

fonts.then(() => {
  createRoot(document.getElementById('root')!).render(
    <StrictMode>
      <QueryClientProvider client={qc}>
        <ThemeProvider>
          <BrowserRouter basename="/ui3">
            <Routes>
              <Route element={<Shell />}>
                <Route index element={<Dashboard />} />
                {PAGES.map(([p, t]) => <Route key={p} path={p} element={<Placeholder title={t} />} />)}
              </Route>
            </Routes>
          </BrowserRouter>
        </ThemeProvider>
      </QueryClientProvider>
    </StrictMode>,
  )
})
