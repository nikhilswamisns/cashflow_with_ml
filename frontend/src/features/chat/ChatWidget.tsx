import { useEffect } from 'react'
import { Maximize2, MessageSquare, RotateCcw, X } from 'lucide-react'
import { useLocation, useNavigate } from 'react-router-dom'
import { useRun } from '@/features/runs/RunProvider'
import { ChatThread } from '@/features/chat/ChatThread'
import { useChat } from '@/features/chat/ChatProvider'

interface Props {
  open: boolean
  setOpen: (o: boolean) => void
}

/** The corner popup. On the Ask Gutster page it hides, because the page is the same chat. */
export function ChatWidget({ open, setOpen }: Props) {
  const { run } = useRun()
  const { msgs, clear } = useChat()
  const { pathname, search } = useLocation()
  const nav = useNavigate()
  const onPage = pathname === '/chat'
  const runLabel = run?.label ?? ''
  useEffect(() => {
    const esc = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setOpen(false)
    }
    document.addEventListener('keydown', esc)
    return () => document.removeEventListener('keydown', esc)
  }, [setOpen])
  if (onPage) return null

  return (
    <>
      <button className={`chat-fab ${open ? 'hide' : ''}`} onClick={() => setOpen(true)} aria-label="Open Ask Gutster">
        <MessageSquare size={20} />
        <span>Ask Gutster</span>
      </button>
      {open && (
        <section className="chat-pop" role="dialog" aria-label="Ask Gutster">
          <div className="card-head tight">
            <div className="ask-title">
              <span className="ask-mark">
                <MessageSquare size={16} />
              </span>
              <h2>Ask Gutster</h2>
            </div>
            <span className="pill soft">Run {runLabel.replace(/,? 20\d\d$/, '')}</span>
            {msgs.length > 0 && (
              <button className="icon-btn" aria-label="New chat" title="New chat" onClick={clear}>
                <RotateCcw size={16} />
              </button>
            )}
            <button
              className="icon-btn"
              aria-label="Open as a full page"
              title="Open as a full page"
              onClick={() => {
                setOpen(false)
                nav({ pathname: '/chat', search })
              }}
            >
              <Maximize2 size={16} />
            </button>
            <button className="icon-btn" aria-label="Close chat" onClick={() => setOpen(false)}>
              <X size={18} />
            </button>
          </div>
          <ChatThread active={open} />
        </section>
      )}
    </>
  )
}
