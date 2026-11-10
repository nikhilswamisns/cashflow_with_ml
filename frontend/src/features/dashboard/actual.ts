import type { Actuals } from '@/features/dashboard/types'

const addDays = (iso: string, n: number) => {
  const d = new Date(iso + 'T00:00:00Z')
  d.setUTCDate(d.getUTCDate() + n)
  return d.toISOString().slice(0, 10)
}

/** Chart slots: the day the run was made (opening cash), then `count` week-ending Fridays from the first one. */
export const slotDates = (startDate: string, firstWeek: string, count: number): string[] => [
  startDate,
  ...Array.from({ length: count }, (_, i) => addDays(firstWeek, i * 7)),
]

/** Actual balance per slot. Today's balance sits in the week still in progress (the next Friday) and is flagged. */
export function actualValues(slots: string[], a: Actuals): { values: (number | null)[]; todayIdx: number | null } {
  const byDate = new Map(a.points.filter((p) => p.kind === 'week_end').map((p) => [p.date, p.balance]))
  const start = a.points.find((p) => p.kind === 'start')
  const values = slots.map((w, i) => (i === 0 ? (start?.balance ?? null) : (byDate.get(w) ?? null)))
  const today = a.points.find((p) => p.kind === 'today')
  let todayIdx: number | null = null
  if (today) {
    const i = slots.findIndex((w, k) => k > 0 && w > today.date)
    if (i > 0) {
      values[i] = today.balance
      todayIdx = i
    }
  }
  return { values, todayIdx }
}
