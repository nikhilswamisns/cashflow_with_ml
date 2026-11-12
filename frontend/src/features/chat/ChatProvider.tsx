import { createContext, useCallback, useContext, useMemo, useRef, useState, type ReactNode } from 'react'
import { askQuestion, type ChartSpec } from '@/features/chat/api'

export interface Msg {
  q: string
  text: string
  status?: string
  unverified?: string[]
  charts?: ChartSpec[]
  links?: { label: string; to: string }[]
  error?: boolean
  done?: boolean // the stream has ended
  revealed?: boolean // the typed reveal has finished, so charts may show
}
interface ChatState {
  msgs: Msg[]
  busy: boolean
  ask: (q: string) => Promise<void>
  clear: () => void
  markRevealed: (i: number) => void
}
const Ctx = createContext<ChatState | null>(null)

/** One conversation shared by the popup and the Ask Gutster page, so switching between them keeps the thread. */
export function ChatProvider({ children }: { children: ReactNode }) {
  const [msgs, setMsgs] = useState<Msg[]>([])
  const [busy, setBusy] = useState(false)
  const msgsRef = useRef<Msg[]>([])
  msgsRef.current = msgs

  const ask = useCallback(async (q: string) => {
    if (!q.trim() || busy) return
    setBusy(true)
    const prior = msgsRef.current
    const history = prior.filter((m) => !m.error && m.text).flatMap((m) => [{ role: 'user' as const, content: m.q }, { role: 'assistant' as const, content: m.text }])
    const at = prior.length
    const patch = (f: (m: Msg) => Msg) => setMsgs((all) => all.map((x, i) => (i === at ? f(x) : x)))
    setMsgs([...prior, { q, text: '', status: 'Thinking…' }])
    try {
      const full = await askQuestion(history, q, {
        onStatus: (status) => patch((m) => ({ ...m, status })),
        onText: (text) => patch((m) => ({ ...m, text })),
        onUnverified: (unverified) => patch((m) => ({ ...m, unverified })),
        onLink: (l) => patch((m) => ({ ...m, links: [...(m.links ?? []), l] })),
        onChart: (c) => patch((m) => ({ ...m, charts: [...(m.charts ?? []), c] })),
      })
      patch((m) => ({ ...m, status: '', done: true, text: full || 'No answer came back. Try rephrasing.' }))
    } catch (e) {
      patch((m) => ({ ...m, status: '', error: true, done: true, revealed: true, text: e instanceof Error ? e.message : 'Something went wrong.' }))
    } finally {
      setBusy(false)
    }
  }, [busy])

  const clear = useCallback(() => setMsgs([]), [])
  const markRevealed = useCallback((i: number) => setMsgs((all) => all.map((m, k) => (k === i && !m.revealed ? { ...m, revealed: true } : m))), [])
  const value = useMemo(() => ({ msgs, busy, ask, clear, markRevealed }), [msgs, busy, ask, clear, markRevealed])
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>
}

export function useChat(): ChatState {
  const c = useContext(Ctx)
  if (!c) throw new Error('useChat needs ChatProvider')
  return c
}
