import { NavLink, useLocation } from 'react-router-dom'
import { MessageSquare } from 'lucide-react'
import { useRun } from '@/features/runs/RunProvider'
import { CHAT_ENABLED } from '@/features/chat/enabled'
import { NAV } from './nav'
export function Rail({ onAsk, onNavigate }: { onAsk: () => void; onNavigate: () => void }) {
  const { runs, run, selectRun } = useRun()
  const { search } = useLocation() // keeps ?run=<id> when you move between pages
  return (
    <aside className="rail">
      <div className="brand">
        <svg viewBox="0 0 64 64" width="30" height="30" aria-hidden="true">
          <defs>
            <linearGradient id="g" x1="0" y1="0" x2="1" y2="1">
              <stop offset="0" stopColor="#2563eb" />
              <stop offset="1" stopColor="#06b6d4" />
            </linearGradient>
          </defs>
          <rect width="64" height="64" rx="16" fill="url(#g)" />
          <polyline
            points="12,34 25,25 36,29 49,15"
            fill="none"
            stroke="#fff"
            strokeWidth="5"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
        <div>
          <div className="brand-name">Gutster</div>
          <div className="brand-sub">Cash flow</div>
        </div>
      </div>
      <nav className="nav">
        {NAV.map((g, gi) => (
          <div key={g.label} style={{ display: 'contents' }}>
            <div className="nav-label">{g.label}</div>
            {g.items.map(({ to, label, icon: Icon }) => (
              <NavLink
                key={to}
                to={{ pathname: to, search }}
                end={to === '/'}
                className="nav-item"
                onClick={onNavigate}
              >
                <Icon size={18} strokeWidth={1.7} />
                {label}
              </NavLink>
            ))}
            {gi === 0 && CHAT_ENABLED && (
              <>
                <div className="nav-label">Assistant</div>
                <button className="nav-item" onClick={onAsk}>
                  <MessageSquare size={18} strokeWidth={1.7} />
                  Ask Gutster
                </button>
              </>
            )}
          </div>
        ))}
      </nav>
      <div className="rail-foot">
        <div className="run-box">
          <label htmlFor="run">Forecast run</label>
          <select id="run" value={run?.id ?? ''} onChange={(e) => selectRun(e.target.value)}>
            {runs.map((r) => (
              <option key={r.id} value={r.id}>
                {r.label} · {r.syncedLabel.replace('Run created ', 'created ').replace(/,.*/, '')}
              </option>
            ))}
          </select>
        </div>
      </div>
    </aside>
  )
}
