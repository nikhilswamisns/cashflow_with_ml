import { useLocation } from 'react-router-dom'
import * as Menu from '@radix-ui/react-dropdown-menu'
import { ArrowRightFromLine, Download, Menu as MenuIcon, Moon, MoreVertical, RefreshCw, Sun } from 'lucide-react'
import { useTheme } from '@/shared/theme'
import { useRun } from '@/features/runs/RunProvider'
import { exportUrl } from '@/features/runs/api'
import { useSync } from '@/features/sync/SyncProvider'
import { logout } from './api'
import { useUser } from '@/features/shell/hooks'
import { TITLES } from './nav'
export function TopBar({ onOpenNav }: { onOpenNav: () => void }) {
  const { theme, toggle } = useTheme()
  const { run } = useRun()
  const { sync, syncing } = useSync()
  const { data: me } = useUser()
  const { pathname } = useLocation()
  const user = me?.user ?? ''
  return (
    <header className="top">
      <button className="icon-btn only-small" aria-label="Open navigation" onClick={onOpenNav}>
        <MenuIcon size={18} />
      </button>
      <h1>{TITLES[pathname] ?? 'Dashboard'}</h1>
      <div className="top-spacer" />
      {run && (
        <span className="pill ok">
          <i className="dot" />
          <span id="fresh">{run.syncedLabel}</span>
        </span>
      )}
      <button
        className="icon-btn hide-small"
        aria-label="Sync from Zoho"
        data-tip={syncing ? 'Syncing…' : 'Sync from Zoho'}
        disabled={syncing}
        onClick={() => void sync()}
      >
        <RefreshCw size={18} className={syncing ? 'spin' : ''} />
      </button>
      <button
        className="icon-btn hide-small"
        aria-label="Download Excel"
        data-tip="Download Excel"
        disabled={!run}
        onClick={() => {
          if (run) location.href = exportUrl(run.id)
        }}
      >
        <Download size={18} />
      </button>
      <button className="icon-btn" aria-label="Switch theme" data-tip="Switch theme" onClick={toggle}>
        {theme === 'dark' ? <Sun size={18} /> : <Moon size={18} />}
      </button>
      <Menu.Root>
        <Menu.Trigger asChild>
          <button className="icon-btn tip-end" aria-label="More" data-tip="More">
            <MoreVertical size={18} />
          </button>
        </Menu.Trigger>
        <Menu.Portal>
          <Menu.Content className="menu" align="end" sideOffset={8}>
            <Menu.Item className="menu-item show-small" disabled={syncing} onSelect={() => void sync()}>
              <RefreshCw size={18} />
              {syncing ? 'Syncing…' : 'Sync from Zoho'}
            </Menu.Item>
            <Menu.Item
              className="menu-item show-small"
              disabled={!run}
              onSelect={() => {
                if (run) location.href = exportUrl(run.id)
              }}
            >
              <Download size={18} />
              Download Excel
            </Menu.Item>
            <Menu.Separator className="menu-sep" />
            <div className="menu-user">
              <span className="avatar">{(user || '?')[0].toUpperCase()}</span>
              <span>{user || 'Signed in'}</span>
            </div>
            <Menu.Item className="menu-item" onSelect={() => void logout()}>
              <ArrowRightFromLine size={18} />
              Log out
            </Menu.Item>
          </Menu.Content>
        </Menu.Portal>
      </Menu.Root>
    </header>
  )
}
