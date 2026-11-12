import { useCallback, useEffect, useRef, useState } from 'react'
import { api } from '@/shared/api'

export type VoiceState = 'idle' | 'recording' | 'transcribing'
const MAX_SECONDS = 60

const supported = () => typeof navigator !== 'undefined' && !!navigator.mediaDevices?.getUserMedia && typeof MediaRecorder !== 'undefined'

/** Pick a recording format the browser can make and Whisper accepts (Chrome/Firefox: webm, Safari: mp4). */
function pickType(): { mime: string; ext: string } {
  for (const [mime, ext] of [['audio/webm;codecs=opus', 'webm'], ['audio/webm', 'webm'], ['audio/mp4', 'mp4'], ['audio/ogg', 'ogg']] as const) {
    if (MediaRecorder.isTypeSupported(mime)) return { mime, ext }
  }
  return { mime: '', ext: 'webm' }
}

/** Mic recording -> text through the server (Whisper). toggle() starts, then stops and transcribes; onText gets the words. */
export function useVoice(onText: (text: string) => void, onError: (message: string) => void) {
  const [state, setState] = useState<VoiceState>('idle')
  const [seconds, setSeconds] = useState(0)
  const rec = useRef<MediaRecorder | null>(null)
  const stream = useRef<MediaStream | null>(null)
  const chunks = useRef<Blob[]>([])
  const timer = useRef<number>(0)
  const cancelled = useRef(false)
  const opening = useRef(false)
  const cb = useRef({ onText, onError })
  cb.current = { onText, onError }

  const release = useCallback(() => {
    window.clearInterval(timer.current)
    stream.current?.getTracks().forEach((t) => t.stop())
    stream.current = null
  }, [])
  const mounted = useRef(true)
  useEffect(() => {
    mounted.current = true
    return () => {
      mounted.current = false
      cancelled.current = true
      if (rec.current?.state === 'recording') rec.current.stop()
      release()
    }
  }, [release])

  const finish = useCallback(async (type: string, ext: string) => {
    release()
    const blob = new Blob(chunks.current, { type: type || 'audio/webm' })
    chunks.current = []
    if (cancelled.current) return
    if (blob.size < 1200) {
      setState('idle')
      cb.current.onError('I could not hear anything. Hold the button a little longer and try again.')
      return
    }
    setState('transcribing')
    try {
      const fd = new FormData()
      fd.append('audio', blob, `audio.${ext}`)
      const r = await api<{ text: string }>('/chat/transcribe', { method: 'POST', body: fd })
      setState('idle')
      cb.current.onText(r.text)
    } catch (e) {
      setState('idle')
      cb.current.onError(e instanceof Error ? e.message : 'Voice did not work. Try typing.')
    }
  }, [release])

  const toggle = useCallback(async () => {
    if (state === 'transcribing') return
    if (state === 'recording') {
      if (rec.current?.state === 'recording') rec.current.stop()
      release() // switch the microphone off right now, do not wait for the recorder to finish
      return
    }
    if (opening.current) return // a click while the permission prompt is open must not open a second microphone
    opening.current = true
    let s: MediaStream
    try {
      s = await navigator.mediaDevices.getUserMedia({ audio: true })
    } catch {
      opening.current = false
      cb.current.onError('The microphone is blocked. Allow it in the browser address bar (it needs https or localhost).')
      return
    }
    opening.current = false
    if (!mounted.current) {
      s.getTracks().forEach((t) => t.stop())
      return
    }
    stream.current = s
    const { mime, ext } = pickType()
    let r: MediaRecorder
    try {
      r = new MediaRecorder(s, mime ? { mimeType: mime } : undefined)
    } catch {
      release()
      cb.current.onError('Voice is not supported in this browser. Try typing.')
      return
    }
    rec.current = r
    chunks.current = []
    cancelled.current = false
    r.ondataavailable = (e) => e.data.size && chunks.current.push(e.data)
    r.onstop = () => void finish(r.mimeType || mime, ext)
    r.start()
    setSeconds(0)
    setState('recording')
    timer.current = window.setInterval(() => {
      setSeconds((s) => {
        if (s + 1 >= MAX_SECONDS && r.state === 'recording') {
          r.stop()
          release()
        }
        return s + 1
      })
    }, 1000)
  }, [state, finish, release])

  return { state, seconds, toggle, supported: supported() }
}
