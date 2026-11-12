import { useEffect, useRef, useSyncExternalStore } from 'react'

export interface KpiSlide {
  view: string // "Our assumptions" / "AI model"
  value: string
  tone: string // 'neg' | 'pos' | ''
  note: string
}

const SWAP_MS = 3000

const prefersReducedMotion = () => typeof window !== 'undefined' && !!window.matchMedia?.('(prefers-reduced-motion: reduce)').matches

/** One shared "which view is showing" for every swapping card on the page, so they always change together, and a click on any
 *  card's dots, or hovering any card, moves or pauses all of them. One timer drives it while at least one card is on screen. */
const sync = (() => {
  let index = 0
  let hovering = 0
  let cards = 0
  let views = 2
  let timer = 0
  const subs = new Set<() => void>()
  const emit = () => subs.forEach((f) => f())
  const stop = () => {
    window.clearInterval(timer)
    timer = 0
  }
  const refresh = () => {
    if (cards > 0 && hovering === 0 && !prefersReducedMotion()) {
      if (!timer)
        timer = window.setInterval(() => {
          index = (index + 1) % views
          emit()
        }, SWAP_MS)
    } else stop()
  }
  return {
    subscribe: (f: () => void) => {
      subs.add(f)
      return () => void subs.delete(f)
    },
    get: () => index,
    join: (n: number) => {
      cards += 1
      views = Math.max(views, n)
      refresh()
      return () => {
        cards -= 1
        refresh()
      }
    },
    hover: (on: boolean) => {
      hovering = Math.max(0, hovering + (on ? 1 : -1))
      refresh()
    },
    reset: () => {
      stop()
      index = 0
      hovering = 0
      cards = 0
      views = 2
    },
    pick: (k: number) => {
      index = k
      if (timer) {
        stop() // restart the clock so a picked view stays for a full interval
        refresh()
      }
      emit()
    },
  }
})()

/** For tests: forget the shared state. */
export const resetKpiSync = () => sync.reset()

/** One KPI card. With two slides (our assumptions, the AI model) the number swaps every few seconds, pauses while you hover
 *  or focus it, and the dots let you pick. With reduced motion on, both numbers are shown stacked instead of swapping. */
export function KpiCard({ label, slides }: { label: string; slides: KpiSlide[] }) {
  const i = useSyncExternalStore(sync.subscribe, sync.get)
  const reduced = prefersReducedMotion()
  const many = slides.length > 1

  useEffect(() => (many && !reduced ? sync.join(slides.length) : undefined), [many, reduced, slides.length])

  // mouse over or keyboard focus on this card pauses every card; let go of the pause if the card goes away while held
  const held = useRef({ mouse: false, focus: false })
  const hold = (key: 'mouse' | 'focus', on: boolean) => {
    const h = held.current
    const was = h.mouse || h.focus
    h[key] = on
    const now = h.mouse || h.focus
    if (now !== was) sync.hover(now)
  }
  useEffect(
    () => () => {
      if (held.current.mouse || held.current.focus) sync.hover(false)
      held.current = { mouse: false, focus: false }
    },
    [],
  )

  if (!many || reduced) {
    return (
      <div className="kpi">
        <div className="kpi-label">{label}</div>
        {slides.map((s) => (
          <div key={s.view}>
            {many && <div className="kpi-view">{s.view}</div>}
            <div className={`kpi-value ${s.tone}`}>{s.value}</div>
            <div className="kpi-note">{s.note}</div>
          </div>
        ))}
      </div>
    )
  }
  const cur = slides[i % slides.length]
  return (
    <div
      className="kpi kpi-swap"
      onMouseEnter={() => hold('mouse', true)}
      onMouseLeave={() => hold('mouse', false)}
      onFocus={() => hold('focus', true)}
      onBlur={() => hold('focus', false)}
    >
      <div className="kpi-head">
        <div className="kpi-label">{label}</div>
        <div className="kpi-view" key={cur.view}>
          {cur.view}
        </div>
      </div>
      {/* every slide sits in the same grid cell, so the card never changes height while the numbers swap */}
      <div className="kpi-stack" aria-live="off">
        {slides.map((s, k) => (
          <div key={s.view} className={`kpi-slide ${k === i % slides.length ? 'on' : ''}`} aria-hidden={k !== i % slides.length}>
            <div className={`kpi-value ${s.tone}`}>{s.value}</div>
            <div className="kpi-note">{s.note}</div>
          </div>
        ))}
      </div>
      <div className="kpi-dots" role="group" aria-label={`${label}: choose a view`}>
        {slides.map((s, k) => (
          <button
            key={s.view}
            type="button"
            className={k === i % slides.length ? 'on' : ''}
            aria-label={s.view}
            aria-pressed={k === i % slides.length}
            onClick={() => sync.pick(k)}
          />
        ))}
      </div>
    </div>
  )
}
