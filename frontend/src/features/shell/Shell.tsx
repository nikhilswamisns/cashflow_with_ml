import { useEffect, useState } from 'react'
import { Outlet, useLocation } from 'react-router-dom'
import { useRun } from '@/features/runs/RunProvider'
import { OpeningCashDialog } from '@/features/sync/OpeningCashDialog'
import { ChatWidget } from '@/features/chat/ChatWidget'
import { Rail } from './Rail'
import { TopBar } from './TopBar'
import { HealthBanner } from '@/features/shell/HealthBanner'
/** Layout only: rail, top bar, page outlet, and the two overlays that any page can open. */
export function Shell() {
  const { runId } = useRun()
  const { pathname } = useLocation()
  const [navOpenAt, setNavOpenAt] = useState<string | null>(null) // path the drawer was opened on
  const navOpen = navOpenAt === pathname // changing page closes it
  const setNavOpen = (o: boolean) => setNavOpenAt(o ? pathname : null)
  const [chatOpen, setChatOpen] = useState(false)
  const [ocOpen, setOcOpen] = useState(false)

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
        <TopBar onOpenNav={() => setNavOpen(true)} onSetOpeningCash={() => setOcOpen(true)} />
        <HealthBanner />
        <Outlet />
      </div>
      {runId && <OpeningCashDialog runId={runId} open={ocOpen} onOpenChange={setOcOpen} />}
      <ChatWidget open={chatOpen} setOpen={setChatOpen} />
    </div>
  )
}
