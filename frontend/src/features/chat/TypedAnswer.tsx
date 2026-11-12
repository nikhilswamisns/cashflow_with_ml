import { useEffect, useRef, useState } from 'react'
import { formatAnswer } from '@/features/chat/api'

/** Hide a half-typed **bold** marker so the reveal never shows stray asterisks. */
function trimOpenBold(t: string): string {
  const marks = t.split('**').length - 1
  return marks % 2 === 1 ? t.slice(0, t.lastIndexOf('**')) : t.replace(/\*$/, '')
}

/**
 * Reveals the streamed text at a steady, readable pace (about 110 characters a second, faster when the stream is far
 * ahead) instead of in network-sized lumps. Already-revealed messages render at once. Calls onFinished when the whole
 * text is shown and the stream has ended.
 */
export function TypedAnswer({ text, done, instant, onFinished }: { text: string; done: boolean; instant: boolean; onFinished: () => void }) {
  const [n, setN] = useState(instant ? text.length : 0)
  const target = useRef(text.length)
  const doneRef = useRef(done)
  const fin = useRef(onFinished)
  target.current = text.length
  doneRef.current = done
  fin.current = onFinished
  useEffect(() => {
    if (instant) return
    let raf = 0
    let last = performance.now()
    let pos = 0
    let finished = false
    const tick = (now: number) => {
      const dt = Math.min((now - last) / 1000, 0.1)
      last = now
      const backlog = target.current - pos
      if (backlog > 0) {
        pos = Math.min(target.current, pos + dt * (110 + backlog * 2))
        setN(Math.floor(pos))
      } else if (doneRef.current && !finished) {
        finished = true
        fin.current()
        return
      }
      raf = requestAnimationFrame(tick)
    }
    raf = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(raf)
  }, [instant])
  const shown = instant || n >= text.length ? text : trimOpenBold(text.slice(0, n))
  return <span dangerouslySetInnerHTML={{ __html: formatAnswer(shown) }} />
}
