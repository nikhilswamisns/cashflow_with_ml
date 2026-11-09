import { useLocation } from 'react-router-dom'

export function Placeholder({ title }: { title: string }) {
  useLocation()
  return (
    <main className="page">
      <div className="card placeholder"><h2>{title}</h2><p>Not part of Step A. It arrives in a later phase.</p></div>
    </main>
  )
}
