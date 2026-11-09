import { useEffect, useState } from 'react'
import { NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom'
import * as Menu from '@radix-ui/react-dropdown-menu'
import { ArrowRightFromLine, Banknote, Database, Download, LayoutDashboard, Menu as MenuIcon, MessageSquare, Moon, MoreVertical, RefreshCw, SlidersHorizontal, Sun, Table2, TrendingUp, type LucideIcon } from 'lucide-react'
import { useTheme } from '../lib/theme'
import { useDashboard, useRuns, useUser } from '../data/hooks'
import { exportUrl, logout, syncZoho } from '../data/source'
import { useQueryClient } from '@tanstack/react-query'
import { useDismissToast, useToast } from '../lib/toast'
import { OpeningCashDialog } from './OpeningCashDialog'
import { HealthBanner } from './HealthBanner'
import { ChatWidget } from './ChatWidget'

export interface ShellCtx { runId: string; afterRun: (id: string) => Promise<void>; sync: (runDate?: string) => Promise<void>; syncing: boolean }
const NAV: { label: string; items: [string, string, LucideIcon][] }[] = [
  { label: 'Forecast', items: [['/', 'Dashboard', LayoutDashboard], ['/matrix', 'Cash forecast', Table2], ['/revenue', 'Revenue forecast', TrendingUp]] },
  { label: 'Workspace', items: [['/data', 'Data & sync', Database], ['/assumptions', 'Assumptions', SlidersHorizontal]] },
]
const TITLES: Record<string, string> = Object.fromEntries(NAV.flatMap((g) => g.items.map(([p, l]) => [p, l])))

export function Shell() {
  const { theme, toggle } = useTheme()
  const { data: runs = [] } = useRuns()
  const [runId, setRunId] = useState('')
  const [open, setOpen] = useState(false)
  const [chatOpen, setChatOpen] = useState(false)
  const [ocOpen, setOcOpen] = useState(false)
  const [syncing, setSyncing] = useState(false)
  const qc = useQueryClient()
  const toast = useToast()
  const dismiss = useDismissToast()
  const loc = useLocation()
  const navigate = useNavigate()
  const run = runs.find((r) => r.id === runId) ?? runs[0]
  const { data: dash } = useDashboard(run?.id ?? '')
  const { data: me } = useUser()
  const user = me?.user ?? ''

  // every way of creating a run ends here: refresh the run list, select the new run, show its dashboard
  async function afterRun(id: string) {
    await qc.invalidateQueries({ queryKey: ['runs'] })
    setRunId(id)
    navigate('/')
  }

  async function sync(runDate?: string) {
    if (syncing) return
    setSyncing(true)
    const wait = toast('Syncing from Zoho… this can take a minute.', 'info', 0)
    try {
      const r = await syncZoho(runDate)
      await afterRun(r.run_id)
      toast(`Synced from Zoho. New run created${r.live_opening_cash ? ` (live bank $${Math.round(r.live_opening_cash).toLocaleString('en-US')})` : ''}.`, 'ok')
    } catch (e) { toast(/\(500\)/.test((e as Error).message) ? 'Zoho sync failed on the server (500). Check the Zoho connection and the server log.' : 'Zoho sync: ' + (e as Error).message, 'error', 8000) }
    finally { dismiss(wait); setSyncing(false) }
  }

  useEffect(() => { if (!runId && runs[0]) setRunId(runs[0].id) }, [runs, runId])
  useEffect(() => { setOpen(false) }, [loc.pathname])
  useEffect(() => {
    const esc = (e: KeyboardEvent) => { if (e.key === 'Escape') setOpen(false) }
    document.addEventListener('keydown', esc)
    return () => document.removeEventListener('keydown', esc)
  }, [])

  return (
    <div className={`app ${open ? 'nav-open' : ''}`}>
      <div className="scrim" onClick={() => setOpen(false)} />
      <aside className="rail">
        <div className="brand">
          <svg viewBox="0 0 64 64" width="30" height="30" aria-hidden="true"><defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stopColor="#2563eb" /><stop offset="1" stopColor="#06b6d4" /></linearGradient></defs><rect width="64" height="64" rx="16" fill="url(#g)" /><polyline points="12,34 25,25 36,29 49,15" fill="none" stroke="#fff" strokeWidth="5" strokeLinecap="round" strokeLinejoin="round" /></svg>
          <div><div className="brand-name">Gutster</div><div className="brand-sub">Cash flow</div></div>
        </div>
        <nav className="nav">
          {NAV.map((g, gi) => (
            <div key={g.label} style={{ display: 'contents' }}>
              <div className="nav-label">{g.label}</div>
              {g.items.map(([to, label, Icon]) => (
                <NavLink key={to} to={to} end={to === '/'} className="nav-item"><Icon size={18} strokeWidth={1.7} />{label}</NavLink>
              ))}
              {gi === 0 && (<>
                <div className="nav-label">Assistant</div>
                <button className="nav-item" onClick={() => { setOpen(false); setChatOpen(true) }}><MessageSquare size={18} strokeWidth={1.7} />Ask Gutster</button>
              </>)}
            </div>
          ))}
        </nav>
        <div className="rail-foot">
          <div className="run-box">
            <label htmlFor="run">Forecast run</label>
            <select id="run" value={run?.id ?? ''} onChange={(e) => setRunId(e.target.value)}>
              {runs.map((r) => <option key={r.id} value={r.id}>{r.label} · {r.syncedLabel.replace('Run created ', 'created ').replace(/,.*/, '')}</option>)}
            </select>
          </div>
        </div>
      </aside>

      <div className="main">
        <header className="top">
          <button className="icon-btn only-small" aria-label="Open navigation" onClick={() => setOpen(true)}><MenuIcon size={18} /></button>
          <h1>{TITLES[loc.pathname] ?? 'Dashboard'}</h1>
          <div className="top-spacer" />
          {run && <span className="pill ok"><i className="dot" /><span id="fresh">{run.syncedLabel}</span></span>}
          <button className="icon-btn" aria-label="Switch theme" title="Switch theme" onClick={toggle}>{theme === 'dark' ? <Sun size={18} /> : <Moon size={18} />}</button>
          <Menu.Root>
            <Menu.Trigger asChild><button className="icon-btn" aria-label="More"><MoreVertical size={18} /></button></Menu.Trigger>
            <Menu.Portal>
              <Menu.Content className="menu" align="end" sideOffset={8}>
                <Menu.Item className="menu-item" disabled={syncing} onSelect={() => void sync()}><RefreshCw size={18} />{syncing ? 'Syncing…' : 'Sync from Zoho'}</Menu.Item>
                <Menu.Item className="menu-item" disabled={!run} onSelect={() => { if (run) location.href = exportUrl(run.id) }}><Download size={18} />Export to Excel</Menu.Item>
                <Menu.Item className="menu-item" disabled={!run} onSelect={() => setOcOpen(true)}><Banknote size={18} />Set opening cash</Menu.Item>
                <Menu.Separator className="menu-sep" />
                <div className="menu-user"><span className="avatar">{(user || '?')[0].toUpperCase()}</span><span>{user || 'Signed in'}</span></div>
                <Menu.Item className="menu-item" onSelect={() => void logout()}><ArrowRightFromLine size={18} />Log out</Menu.Item>
              </Menu.Content>
            </Menu.Portal>
          </Menu.Root>
        </header>
        <HealthBanner />
        <Outlet context={{ runId: run?.id ?? '', afterRun, sync, syncing } satisfies ShellCtx} />
      </div>
      {run && <OpeningCashDialog runId={run.id} open={ocOpen} onOpenChange={setOcOpen} />}
      {dash && run && <ChatWidget d={dash} runId={run.id} runLabel={run.label} open={chatOpen} setOpen={setChatOpen} />}
    </div>
  )
}
