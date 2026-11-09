import { createContext, useCallback, useContext, useState, type ReactNode } from 'react'

type Kind = 'info' | 'ok' | 'error'
interface Toast { id: number; kind: Kind; text: string }
const Ctx = createContext<(text: string, kind?: Kind, ms?: number) => number>(() => 0)
const Dismiss = createContext<(id: number) => void>(() => {})
let next = 1

export function ToastProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<Toast[]>([])
  const dismiss = useCallback((id: number) => setItems((l) => l.filter((t) => t.id !== id)), [])
  const push = useCallback((text: string, kind: Kind = 'info', ms = 5000) => {
    const id = next++
    setItems((l) => [...l, { id, kind, text }])
    if (ms > 0) setTimeout(() => dismiss(id), ms)
    return id
  }, [dismiss])
  return (
    <Ctx.Provider value={push}><Dismiss.Provider value={dismiss}>
      {children}
      <div className="toasts" role="status" aria-live="polite">
        {items.map((t) => <div key={t.id} className={`toast ${t.kind}`}>{t.text}</div>)}
      </div>
    </Dismiss.Provider></Ctx.Provider>
  )
}
export const useToast = () => useContext(Ctx)
export const useDismissToast = () => useContext(Dismiss)
