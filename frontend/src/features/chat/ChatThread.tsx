import { useEffect, useRef, useState, type FormEvent } from 'react'
import { Link } from 'react-router-dom'
import { Loader2, Mic, Send, Square } from 'lucide-react'
import { TypedAnswer } from '@/features/chat/TypedAnswer'
import { ChatChart } from '@/features/chat/ChatChart'
import { useChat } from '@/features/chat/ChatProvider'
import { useVoice } from '@/features/chat/useVoice'

const STARTERS = [
  'What will cash be this coming week?',
  'Where is our cash going?',
  'Which customers pay slowest?',
  'What should I chase this week?',
]

/** Messages, starter questions (only while the chat is empty) and the input. Used by the popup and the page. */
export function ChatThread({ active = true }: { active?: boolean }) {
  const { msgs, busy, ask, markRevealed } = useChat()
  const [text, setText] = useState('')
  const [voiceError, setVoiceError] = useState('')
  const voice = useVoice(
    (t) => {
      setVoiceError('')
      void ask(t)
    },
    setVoiceError,
  )
  const end = useRef<HTMLDivElement>(null)
  useEffect(() => {
    if (active) end.current?.scrollIntoView({ block: 'end' })
  }, [msgs, active])
  const submit = (e: FormEvent) => {
    e.preventDefault()
    const q = text
    setText('')
    void ask(q)
  }
  return (
    <>
      <div className="thread" aria-live="polite">
        {msgs.length === 0 && (
          <div className="starters">
            <p>Ask about your cash forecast, what customers owe, who pays slowly, or what to chase this week.</p>
            <div className="chips">
              {STARTERS.map((c) => (
                <button key={c} disabled={busy} onClick={() => void ask(c)}>
                  {c}
                </button>
              ))}
            </div>
          </div>
        )}
        {msgs.map((m, i) => (
          <div key={i} style={{ display: 'contents' }}>
            <div className="msg-q">{m.q}</div>
            <div className={`msg-a ${m.error ? 'err' : ''}`}>
              {m.error ? <p>{m.text}</p> : <TypedAnswer text={m.text} done={!!m.done} instant={!!m.revealed} onFinished={() => markRevealed(i)} />}
              {m.revealed && m.charts?.map((c, k) => <ChatChart key={c.title} spec={c} delay={k * 0.15} />)}
              {m.revealed && !!m.links?.length && (
                <div className="chat-links">
                  {m.links.map((l) => (
                    <Link key={l.to} to={l.to}>
                      {l.label} →
                    </Link>
                  ))}
                </div>
              )}
              {m.status && <div className="status">{m.status}</div>}
              {m.revealed && !!m.unverified?.length && (
                <div className="warn">Check these figures against the dashboard, they could not be matched to the data: {m.unverified.join(', ')}</div>
              )}
            </div>
          </div>
        ))}
        <div ref={end} />
      </div>
      {(voice.state !== 'idle' || voiceError) && (
        <div className={`voice-note ${voiceError ? 'err' : ''}`} role="status">
          {voiceError ||
            (voice.state === 'recording'
              ? `Listening… ${voice.seconds}s. Tap the square to send.`
              : 'Turning your voice into text…')}
        </div>
      )}
      <form className="composer" onSubmit={submit}>
        <input value={text} onChange={(e) => setText(e.target.value)} placeholder="Ask about cash, customers, payments…" autoComplete="off" aria-label="Ask a question" />
        <button
          type="button"
          className={`icon-btn mic ${voice.state}`}
          aria-label={voice.state === 'recording' ? 'Stop and send' : 'Speak your question'}
          title={!voice.supported ? 'Voice is not supported in this browser' : voice.state === 'recording' ? 'Tap to stop and send' : 'Speak your question'}
          disabled={!voice.supported || busy || voice.state === 'transcribing'}
          onClick={() => {
            setVoiceError('')
            void voice.toggle()
          }}
        >
          {voice.state === 'recording' ? <Square size={16} /> : voice.state === 'transcribing' ? <Loader2 size={18} className="spin" /> : <Mic size={18} />}
        </button>
        <button type="submit" className="send" aria-label="Send" disabled={busy}>
          <Send size={18} />
        </button>
      </form>
      <p className="fine">Answers use only your forecast and Zoho data. Read-only: this chat cannot change anything.</p>
    </>
  )
}
