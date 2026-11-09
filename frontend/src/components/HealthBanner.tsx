import { useState } from 'react'
import { X } from 'lucide-react'
import { useHealth } from '../data/hooks'

// Same idea as /ui2: say why something is missing instead of leaving panels empty.
export function HealthBanner() {
  const { data } = useHealth()
  const [hidden, setHidden] = useState(false)
  if (!data || data.status === 'ok' || hidden) return null
  const bad = data.status === 'broken'
  return (
    <div className={`health-banner ${bad ? 'bad' : ''}`} role="alert">
      <strong>{bad ? 'This server is missing files the dashboard needs.' : 'Some optional features are switched off on this server.'}</strong>
      <ul>
        {data.checks.filter((c) => !c.ok).map((c) => (
          <li key={c.name}><b>{c.name}</b>{c.required ? '' : ' (optional)'}: {c.detail}{c.fix ? `. ${c.fix}` : ''}</li>
        ))}
      </ul>
      <button aria-label="Dismiss" onClick={() => setHidden(true)}><X size={16} /></button>
    </div>
  )
}
