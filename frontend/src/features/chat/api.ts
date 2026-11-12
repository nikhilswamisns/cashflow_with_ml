
const TOOL_STATUS: Record<string, string> = {
  cash_outlook: 'Checking the cash forecast…',
  outflows_by_purpose: 'Looking at where cash goes…',
  customer_payments: 'Reading the payment history…',
  rank_customers: 'Ranking customers by payment speed…',
  working_capital: 'Checking receivables and payables…',
  actions: 'Checking open invoices and bills…',
}

const esc = (s: string) => s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')

/** The model returns plain text with **bold** and "-" bullets. Escape everything first, then add only those two tags. */
export function formatAnswer(text: string): string {
  const lines = esc(text).split('\n')
  const out: string[] = []
  let list = false
  for (const raw of lines) {
    const line = raw.replace(/\*\*(.+?)\*\*/g, '<b>$1</b>')
    const bullet = /^\s*[-*•]\s+(.*)$/.exec(line)
    if (bullet) {
      if (!list) out.push('<ul>')
      list = true
      out.push(`<li>${bullet[1]}</li>`)
    } else {
      if (list) out.push('</ul>')
      list = false
      if (line.trim()) out.push(`<p>${line}</p>`)
    }
  }
  if (list) out.push('</ul>')
  return out.join('')
}

export interface ChartSpec {
  kind: 'doughnut' | 'bar'
  title: string
  labels: string[]
  values: number[]
  signed?: boolean
  series?: [string, string]
  values2?: number[]
}

interface Handlers {
  onStatus: (s: string) => void
  onText: (full: string) => void
  onUnverified: (figures: string[]) => void
  onChart: (c: ChartSpec) => void
  onLink?: (l: { label: string; to: string }) => void
}

/** Streams the answer (one JSON event per line). Resolves with the final text; throws with a readable message. */
export async function askQuestion(
  history: { role: 'user' | 'assistant'; content: string }[],
  question: string,
  h: Handlers,
  signal?: AbortSignal,
): Promise<string> {
  const res = await fetch('/api/chat', {
    method: 'POST',
    credentials: 'same-origin',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ question, history }),
    signal,
  })
  if (res.status === 401) {
    location.href = `/login?next=${encodeURIComponent(location.pathname)}`
    throw new Error('Not logged in')
  }
  if (!res.ok || !res.body) throw new Error(res.status === 404 ? 'Chat is not available on this server yet.' : `Chat failed (${res.status})`)
  const reader = res.body.getReader()
  const dec = new TextDecoder()
  let buf = ''
  let text = ''
  for (;;) {
    const { done, value } = await reader.read()
    if (done) break
    buf += dec.decode(value, { stream: true })
    let nl: number
    while ((nl = buf.indexOf('\n')) >= 0) {
      const line = buf.slice(0, nl).trim()
      buf = buf.slice(nl + 1)
      if (!line) continue
      const e = JSON.parse(line) as { type: string; text?: string; tool?: string; message?: string; unverified?: string[]; chart?: ChartSpec; label?: string; to?: string }
      if (e.type === 'tool') h.onStatus(TOOL_STATUS[e.tool ?? ''] ?? 'Looking at your data…')
      else if (e.type === 'delta') {
        text += e.text ?? ''
        h.onStatus('')
        h.onText(text)
      } else if (e.type === 'chart' && e.chart) h.onChart(e.chart)
      else if (e.type === 'link' && e.label && e.to) h.onLink?.({ label: e.label, to: e.to })
      else if (e.type === 'check') h.onUnverified(e.unverified ?? [])
      else if (e.type === 'error') throw new Error(e.message || 'Something went wrong.')
    }
  }
  return text
}
