import { RotateCcw } from 'lucide-react'
import { ChatThread } from '@/features/chat/ChatThread'
import { useChat } from '@/features/chat/ChatProvider'

/** Ask Gutster as a full page: fills the whole tab; same conversation as the popup. */
export function ChatPage() {
  const { msgs, clear } = useChat()
  return (
    <main className="page chat-page">
      <div className="chat-head">
        <p className="sub">Questions about your forecast and Zoho data. Read-only.</p>
        {msgs.length > 0 && (
          <button className="btn" onClick={clear}>
            <RotateCcw size={14} /> New chat
          </button>
        )}
      </div>
      <div className="chat-body">
        <ChatThread />
      </div>
    </main>
  )
}
