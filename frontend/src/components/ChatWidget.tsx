import { useEffect, useRef, useState, type FormEvent } from 'react'
import { Mic, Send, MessageSquare, X } from 'lucide-react'
import type { DashboardData } from '../data/types'
import { askQuestion } from '../data/source'
import { dlabel, usd } from '../lib/format'

interface Msg { q: string; html: string; source: string }
const CHIPS = ['Which week is the lowest?', 'Total payments from a client', 'Which client pays best?']

interface Props { d: DashboardData; runId: string; runLabel: string; open: boolean; setOpen: (o: boolean) => void }

export function ChatWidget({ d, runId, runLabel, open, setOpen }: Props) {
  const first: Msg = {
    q: 'What will cash be this coming week?',
    html: `Cash is forecast to end the week of <b>${dlabel(d.labels[0])}</b> at <b>${usd(d.cash_rules[0])}</b> on the standard timing rules${d.ml ? `, or <b>${usd(d.ml.cash_ml[0])}</b> if customers pay the way they usually do (ML timing)` : ''}.`,
    source: `Used: forecast run ${runLabel}, week 1 · same run`,
  }
  const [msgs, setMsgs] = useState<Msg[]>([first])
  const [text, setText] = useState('')
  const end = useRef<HTMLDivElement>(null)
  useEffect(() => { if (open) end.current?.scrollIntoView({ block: 'end' }) }, [msgs, open])
  useEffect(() => {
    const esc = (e: KeyboardEvent) => { if (e.key === 'Escape') setOpen(false) }
    document.addEventListener('keydown', esc)
    return () => document.removeEventListener('keydown', esc)
  }, [setOpen])

  async function ask(q: string) {
    if (!q.trim()) return
    const a = await askQuestion(runId, q)
    setMsgs((m) => [...m, { q, ...a }])
    setText('')
  }
  const submit = (e: FormEvent) => { e.preventDefault(); void ask(text) }

  return (
    <>
      <button className={`chat-fab ${open ? 'hide' : ''}`} onClick={() => setOpen(true)} aria-label="Open Ask Gutster">
        <MessageSquare size={20} /><span>Ask Gutster</span>
      </button>
      {open && (
    <section className="chat-pop" role="dialog" aria-label="Ask Gutster">
      <div className="card-head tight">
        <div className="ask-title"><span className="ask-mark"><MessageSquare size={16} /></span><h2>Ask Gutster</h2></div>
        <span className="pill soft" title="Every answer names the run and sync time it used">Run {runLabel.replace(/ 20\d\d$/, '')}</span>
        <button className="icon-btn" aria-label="Close chat" onClick={() => setOpen(false)}><X size={18} /></button>
      </div>
      <div className="thread" aria-live="polite">
        {msgs.map((m, i) => (
          <div key={i} style={{ display: 'contents' }}>
            <div className="msg-q">{m.q}</div>
            <div className="msg-a"><span dangerouslySetInnerHTML={{ __html: m.html }} /><div className="src">{m.source}</div></div>
          </div>
        ))}
        <div ref={end} />
      </div>
      <div className="chips">{CHIPS.map((c) => <button key={c} onClick={() => void ask(c)}>{c}</button>)}</div>
      <form className="composer" onSubmit={submit}>
        <input value={text} onChange={(e) => setText(e.target.value)} placeholder="Ask about cash, customers, payments…" autoComplete="off" aria-label="Ask a question" />
        <button type="button" className="icon-btn" aria-label="Speak" title="Speak your question"><Mic size={18} /></button>
        <button type="submit" className="send" aria-label="Send"><Send size={18} /></button>
      </form>
      <p className="fine">Sample answer. Figures come from the forecast engine, not from the model.</p>
    </section>
      )}
    </>
  )
}
