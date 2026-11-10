import { useEffect, useState } from 'react'
import { Outlet, useLocation } from 'react-router-dom'
import { ChatWidget } from '@/features/chat/ChatWidget'
import { CHAT_ENABLED } from '@/features/chat/enabled'
import { Rail } from './Rail'
import { TopBar } from './TopBar'
/** Layout only: rail, top bar, page outlet, and the chat overlay. */
export function Shell() {
  const { pathname } = useLocation()
  const [navOpenAt, setNavOpenAt] = useState<string | null>(null) // path the drawer was opened on
  const navOpen = navOpenAt === pathname // changing page closes it
  const setNavOpen = (o: boolean) => setNavOpenAt(o ? pathname : null)
  const [chatOpen, setChatOpen] = useState(false)

  useEffect(() => {
    const esc = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setNavOpenAt(null)
    }
    document.addEventListener('keydown', esc)
    return () => document.removeEventListener('keydown', esc)
  }, [])

  return (
    <div className={`app ${navOpen ? 'nav-open' : ''}`}>
      <div className="scrim" onClick={() => setNavOpen(false)} />
      <Rail
        onAsk={() => {
          setNavOpen(false)
          setChatOpen(true)
        }}
        onNavigate={() => setNavOpen(false)}
      />
      <div className="main">
        <TopBar onOpenNav={() => setNavOpen(true)} />
        <Outlet />
      </div>
      {CHAT_ENABLED && <ChatWidget open={chatOpen} setOpen={setChatOpen} />}
    </div>
  )
}
