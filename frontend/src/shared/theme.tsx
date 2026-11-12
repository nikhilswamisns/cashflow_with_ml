import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from 'react'

export type Theme = 'light' | 'vercel'
// label + two swatch colours (background, accent) for the picker
export const THEMES: { id: Theme; label: string; bg: string; accent: string }[] = [
  { id: 'light', label: 'Light', bg: '#f4f6f9', accent: '#2563eb' },
  { id: 'vercel', label: 'Black', bg: '#000000', accent: '#ededed' },
]
const IDS = THEMES.map((t) => t.id)
const Ctx = createContext<{ theme: Theme; setTheme: (t: Theme) => void }>({ theme: 'light', setTheme: () => {} })

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [theme, setThemeState] = useState<Theme>(() => {
    const t = document.documentElement.dataset.theme as Theme
    if (IDS.includes(t)) return t
    document.documentElement.dataset.theme = 'light' // a theme that no longer exists (e.g. an old saved 'dark')
    return 'light'
  })
  const setTheme = useCallback((next: Theme) => {
    document.documentElement.dataset.theme = next // set first so charts read the new CSS variables
    try {
      localStorage.setItem('ui3-theme', next)
    } catch {
      /* private mode */
    }
    setThemeState(next)
  }, [])
  const value = useMemo(() => ({ theme, setTheme }), [theme, setTheme])
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>
}
export const useTheme = () => useContext(Ctx)
